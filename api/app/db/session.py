"""Engine + session factory — the thin data-access primitive (US-E3-04).

Reads ``settings.database_url`` (env-driven; no creds in code). Business logic and
repositories are Orion's (Day 6); this module just provides a configured engine, a
``sessionmaker``, and a context-managed session so the seed script and future
services share one connection setup.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def make_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    """Build a SQLAlchemy Engine for the given (or configured) database URL."""
    return create_engine(
        url or settings.database_url,
        echo=echo,
        pool_pre_ping=True,
        future=True,
    )


# Module-level engine + factory for the default (configured) database.
engine: Engine = make_engine()
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False, future=True
)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, rollback on error, always close."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
