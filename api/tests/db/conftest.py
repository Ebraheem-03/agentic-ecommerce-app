"""Pytest fixtures for the Alembic migration contract (US-QA-D04).

These tests need a *throwaway* Postgres database so that upgrade/downgrade can be
exercised destructively without touching any dev/seed data. The strategy:

1. Read the admin connection from ``TEST_DATABASE_URL`` (preferred) or
   ``DATABASE_URL`` (the same env the app + Alembic use). The connection points at
   a live pgvector-enabled Postgres (docker-compose ``db`` service, or the CI
   Postgres service).
2. ``CREATE DATABASE hearth_mig_test_<rand>`` on that server via an AUTOCOMMIT
   connection to the ``postgres`` maintenance DB.
3. Hand the per-test code an Alembic ``Config`` pointed at that fresh DB plus a
   psycopg connection for introspection.
4. ``DROP DATABASE`` on teardown — nothing leaks.

No credentials are hard-coded: everything derives from the env URL (see repo-root
``.env.example``). See docs/qa/db-migration-test-plan.md and ADR-0019.
"""

from __future__ import annotations

import importlib
import os
import secrets
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from alembic.config import Config
from psycopg import Connection
from sqlalchemy.engine.url import make_url

import app.core.config as app_config

# api/ project root (this file is api/tests/db/conftest.py).
API_ROOT = Path(__file__).resolve().parents[2]


def _admin_url() -> str:
    """The env-driven connection string for a live, pgvector-enabled Postgres.

    Prefers ``TEST_DATABASE_URL`` so a runner can point migration tests at a
    disposable server without disturbing ``DATABASE_URL``. Falls back to
    ``DATABASE_URL`` (what Alembic/the app already read).
    """
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip(
            "No TEST_DATABASE_URL/DATABASE_URL set — migration tests need a live "
            "pgvector Postgres (docker-compose `db` or CI service). Skipping."
        )
    return url


def _libpq_dsn(url: str) -> str:
    """Strip SQLAlchemy's ``+psycopg`` driver suffix for a raw psycopg connection."""
    return make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)


@pytest.fixture
def migration_db() -> Iterator[tuple[Config, str]]:
    """Create a throwaway database, yield (alembic Config, libpq DSN), then drop it.

    The yielded Alembic ``Config`` is fully wired to the throwaway DB so callers
    can run ``command.upgrade(cfg, "head")`` / ``downgrade(cfg, "base")`` directly.
    The DSN is for opening an introspection connection with psycopg.
    """
    base = make_url(_admin_url())
    db_name = f"hearth_mig_test_{secrets.token_hex(6)}"

    # Connect to the maintenance DB in autocommit to issue CREATE/DROP DATABASE.
    maint = base.set(database="postgres", drivername="postgresql")
    with psycopg.connect(maint.render_as_string(hide_password=False), autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{db_name}"')

    target = base.set(database=db_name, drivername="postgresql+psycopg")
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    # env.py reads settings.database_url; override via env so the Config and the
    # migration env agree on the throwaway DB.
    prev = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = target.render_as_string(hide_password=False)
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    # `app.core.config.settings` is a module-level singleton frozen at first import;
    # Alembic's env.py reads `settings.database_url`. Reload the module so each
    # throwaway DB is actually targeted (otherwise every test reuses test 1's URL).
    importlib.reload(app_config)

    try:
        yield cfg, _libpq_dsn(os.environ["DATABASE_URL"])
    finally:
        if prev is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prev
        importlib.reload(app_config)
        with psycopg.connect(
            maint.render_as_string(hide_password=False), autocommit=True
        ) as admin:
            # Force-disconnect any lingering sessions, then drop.
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (db_name,),
            )
            admin.execute(f'DROP DATABASE IF EXISTS "{db_name}"')


def open_conn(dsn: str) -> Connection:
    """Open a fresh psycopg connection for introspection queries."""
    return psycopg.connect(dsn)
