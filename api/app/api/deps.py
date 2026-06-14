"""Shared FastAPI dependencies — DB session + Bearer auth resolution (US-E4-05).

Two layers:

* ``get_session`` yields a SQLAlchemy ``Session``. It resolves the engine from the
  *current* ``settings.database_url`` at request time (cached per-URL), rather than the
  module-level engine in ``app.db.session`` frozen at import. This is what lets the ASGI
  test client run against a throwaway test database whose URL is set after import.

* ``require_user`` reads ``Authorization: Bearer <token>``, SHA-256s it, looks up a
  non-expired ``sessions`` row, **bumps ``expires_at`` forward 7 days (sliding window,
  ADR-0023)**, loads the owning user, and returns it. Missing / unknown / expired token
  raises ``APIError(401, unauthenticated)``. ``require_role(*roles)`` builds on it and
  raises ``APIError(403, forbidden)`` on a role mismatch.

The agent layer (Echo) acts under the resolving user's scope by depending on this same
``require_user`` — there is one identity-resolution path for humans and agents alike.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.core.config as app_config
from app.core.errors import APIError
from app.core.security import hash_token
from app.db.models import User
from app.db.models.user import Session as SessionRow
from app.db.session import make_engine
from app.schemas.envelope import ErrorCode

# Sliding-session lifetime: each authenticated request pushes expiry out this far.
SESSION_TTL = timedelta(days=7)

# Cache one engine + sessionmaker per database URL so we don't rebuild a pool per
# request, while still honoring a URL that changes after import (test throwaway DBs).
_ENGINES: dict[str, tuple[Engine, sessionmaker[Session]]] = {}


def _factory_for(url: str) -> sessionmaker[Session]:
    cached = _ENGINES.get(url)
    if cached is None:
        engine = make_engine(url)
        factory: sessionmaker[Session] = sessionmaker(
            bind=engine, autoflush=False, expire_on_commit=False, future=True
        )
        _ENGINES[url] = (engine, factory)
        return factory
    return cached[1]


def get_session() -> Iterator[Session]:
    """Yield a transactional DB session bound to the current ``settings.database_url``.

    Commits on success, rolls back on error, always closes — mirrors ``session_scope``.
    """
    factory = _factory_for(app_config.settings.database_url)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(get_session)]


def _unauthenticated() -> APIError:
    return APIError(
        status_code=401,
        code=ErrorCode.unauthenticated,
        message="You need to be signed in to do that.",
    )


def _resolve_session_row(session: Session, token: str) -> SessionRow:
    """Look up a live session by token, bump its sliding expiry, return the row."""
    token_digest = hash_token(token)
    row = session.scalar(select(SessionRow).where(SessionRow.token_hash == token_digest))
    if row is None:
        raise _unauthenticated()

    now = datetime.now(UTC)
    if row.expires_at <= now:
        # Expired: lazily delete and treat as unauthenticated.
        session.delete(row)
        session.flush()
        raise _unauthenticated()

    # Sliding window: every authenticated request renews the 7-day expiry.
    row.expires_at = now + SESSION_TTL
    session.flush()
    return row


@dataclass(frozen=True, slots=True)
class AuthContext:
    """The resolved identity behind a request: the user and their live session row."""

    user: User
    session_row: SessionRow


def require_auth(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> AuthContext:
    """Resolve user + session from the Bearer token (sliding-renew the session).

    Raises ``APIError(401, unauthenticated)`` when the header is missing/malformed or the
    token is unknown/expired. The base of every protected route and the agent layer.
    """
    if authorization is None:
        raise _unauthenticated()
    scheme, _, raw_token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not raw_token.strip():
        raise _unauthenticated()

    row = _resolve_session_row(session, raw_token.strip())
    user = session.get(User, row.user_id) if row.user_id is not None else None
    if user is None or user.deleted_at is not None or not user.is_active:
        raise _unauthenticated()
    return AuthContext(user=user, session_row=row)


AuthDep = Annotated[AuthContext, Depends(require_auth)]


def require_user(auth: AuthDep) -> User:
    """Resolve just the current user (the common case for protected routes)."""
    return auth.user


CurrentUser = Annotated[User, Depends(require_user)]


def require_role(*roles: str) -> Callable[[User], User]:
    """Dependency factory: require the current user to hold one of ``roles`` (else 403)."""

    def _dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise APIError(
                status_code=403,
                code=ErrorCode.forbidden,
                message="You don't have access to that.",
            )
        return user

    return _dependency
