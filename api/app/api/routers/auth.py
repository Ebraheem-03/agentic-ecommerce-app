"""Auth routes — opaque session-token model (US-E4-04 / US-E4-05, ADR-0023).

Identity is an opaque, server-side **session token** backed by ``sessions(token_hash,
expires_at)``, sent as ``Authorization: Bearer <token>`` — not a JWT, so logout is a row
delete (instant revocation). Passwords are argon2id-hashed; tokens are SHA-256-stored.
Registration creates the account unverified but still mints a session; ``/auth/login`` is
gated on ``email_verified`` (403 while false); ``/auth/verify`` is the demo stub that
flips the flag (no email is actually sent).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api._contract import ERROR_RESPONSES
from app.api.deps import SESSION_TTL, AuthDep, CurrentUser, SessionDep
from app.core.errors import APIError
from app.core.security import (
    hash_password,
    hash_token,
    mint_session_token,
    verify_password,
)
from app.db.models import User
from app.db.models.user import Session as SessionRow
from app.schemas.auth import (
    LoginRequest,
    LogoutResult,
    RegisterRequest,
    SessionOut,
    UserOut,
)
from app.schemas.envelope import Envelope, ErrorCode

router = APIRouter(prefix="/auth", tags=["auth"], responses=ERROR_RESPONSES)


def _user_out(user: User) -> UserOut:
    """Project a ``User`` ORM row onto the public ``UserOut`` view (no password hash)."""
    return UserOut.model_validate(user)


def _mint_session(session: SessionDep, user: User) -> SessionOut:
    """Create a fresh session row for ``user`` and return the one-time token + expiry."""
    token = mint_session_token()
    expires_at = datetime.now(UTC) + SESSION_TTL
    row = SessionRow(user_id=user.id, token_hash=hash_token(token), expires_at=expires_at)
    session.add(row)
    session.flush()
    return SessionOut(token=token, expires_at=expires_at, user=_user_out(user))


@router.post(
    "/register",
    response_model=Envelope[SessionOut],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
)
def register(body: RegisterRequest, session: SessionDep) -> Envelope[SessionOut]:
    """Create a buyer/seller account (unverified) and return a session token. (J-SEL-01)"""
    existing = session.scalar(
        select(User).where(User.email == body.email, User.deleted_at.is_(None))
    )
    if existing is not None:
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code=ErrorCode.email_taken,
            message="That email is already registered.",
        )

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        role=body.role.value,
        email_verified=False,
    )
    session.add(user)
    session.flush()
    return Envelope(data=_mint_session(session, user))


@router.post(
    "/login",
    response_model=Envelope[SessionOut],
    summary="Log in (exchange credentials for a session token)",
)
def login(body: LoginRequest, session: SessionDep) -> Envelope[SessionOut]:
    """Authenticate and mint a session token (403 while email is unverified)."""
    user = session.scalar(
        select(User).where(User.email == body.email, User.deleted_at.is_(None))
    )
    stored_hash = user.password_hash if user is not None else None
    # Always run a verify (dummy when no user) so timing doesn't reveal which failed.
    if not verify_password(stored_hash, body.password) or user is None or not user.is_active:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=ErrorCode.unauthenticated,
            message="That email or password didn't match.",
        )
    if not user.email_verified:
        raise APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            code=ErrorCode.forbidden,
            message="Please verify your email before signing in.",
        )
    return Envelope(data=_mint_session(session, user))


@router.post(
    "/logout",
    response_model=Envelope[LogoutResult],
    summary="Log out (revoke current session)",
)
def logout(auth: AuthDep, session: SessionDep) -> Envelope[LogoutResult]:
    """Revoke the bearer session token (deletes the sessions row)."""
    session.delete(auth.session_row)
    session.flush()
    return Envelope(data=LogoutResult(revoked=True))


@router.get(
    "/me",
    response_model=Envelope[UserOut],
    summary="Current authenticated user",
)
def me(user: CurrentUser) -> Envelope[UserOut]:
    """Return the user behind the current session token."""
    return Envelope(data=_user_out(user))


@router.post(
    "/verify",
    response_model=Envelope[UserOut],
    summary="Verify the current account's email (demo stub)",
)
def verify(user: CurrentUser, session: SessionDep) -> Envelope[UserOut]:
    """Flip ``email_verified`` to true for the current user (no real email sent — demo)."""
    user.email_verified = True
    session.add(user)
    session.flush()
    return Envelope(data=_user_out(user))
