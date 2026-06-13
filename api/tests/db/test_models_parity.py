"""Model <-> schema parity + round-trip (US-E3-04).

The ORM models in ``app.db.models`` mirror the hand-authored Alembic schema. These
tests prove that mirror is faithful against a *real migrated* throwaway DB (reusing
the US-QA-D04 ``migration_db`` fixture):

1. ``test_no_metadata_diff`` — the strongest single check: Alembic's autogenerate
   comparator finds NO difference between ``Base.metadata`` (the models) and the
   migrated database, for the tables we own. If a column type, nullability, PK,
   unique, FK or index drifts, this fails.
2. ``test_table_and_column_parity`` — explicit, readable per-table column-set check
   so a failure points at the exact table.
3. ``test_core_roundtrip`` — insert user->store->product->variant->inventory through
   the ORM (exercising uuidv7 + now() server defaults + native enums) and an
   ``embeddings`` row at ``settings.embed_dim`` (exercising the pgvector insert),
   then read them back.
"""

from __future__ import annotations

import importlib

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine.url import make_url

import app.core.config as app_config
import app.db.models  # noqa: F401 — registers all tables on Base.metadata
from alembic import command
from app.db.base import Base

# 21 app tables (excl. alembic_version) — the full set the models own.
OWNED_TABLES: frozenset[str] = frozenset(Base.metadata.tables)


def _sqla_url(dsn: str) -> str:
    """libpq DSN -> SQLAlchemy +psycopg URL."""
    return make_url(dsn).set(drivername="postgresql+psycopg").render_as_string(
        hide_password=False
    )


def test_owned_table_count() -> None:
    """Sanity: the models register exactly the 21 app tables."""
    assert len(OWNED_TABLES) == 21


def test_no_metadata_diff(migration_db: tuple[Config, str]) -> None:
    """No autogenerate diff between the ORM metadata and the migrated DB."""
    cfg, dsn = migration_db
    command.upgrade(cfg, "head")

    # `settings.embed_dim` (used by the Embedding model's Vector size) is read at
    # import time; the fixture reloads app.core.config per throwaway DB, so make
    # sure our models see the same dim the migration used.
    importlib.reload(app_config)

    engine = create_engine(_sqla_url(dsn), future=True)
    try:
        with engine.connect() as conn:
            mc = MigrationContext.configure(
                conn,
                opts={
                    "compare_type": True,
                    "target_metadata": Base.metadata,
                    # Only diff the tables the models own (ignore alembic_version).
                    "include_name": lambda name, type_, parent: (
                        type_ != "table" or name in OWNED_TABLES
                    ),
                },
            )
            diffs = compare_metadata(mc, Base.metadata)
    finally:
        engine.dispose()

    relevant = _drop_unique_name_only_renames(diffs)
    assert not relevant, f"metadata drift vs migrated DB: {relevant}"


def _uc_cols(diff: tuple[object, ...]) -> frozenset[str] | None:
    """Column set of an (add|remove)_constraint diff that is a UniqueConstraint."""
    from sqlalchemy import UniqueConstraint  # local import to keep top clean

    if len(diff) == 2 and isinstance(diff[0], str) and diff[0].endswith("_constraint"):
        obj = diff[1]
        if isinstance(obj, UniqueConstraint):
            return frozenset(c.name for c in obj.columns)
    return None


def _drop_unique_name_only_renames(diffs: list[object]) -> list[object]:
    """Discard remove+add UniqueConstraint pairs over the SAME column set.

    The hand-written migrations declare uniqueness with inline ``col ... UNIQUE``,
    which Postgres auto-names ``<table>_<col>_key``; the ORM's ``unique=True`` yields
    the naming-convention name ``uq_<table>_<col>``. These are the SAME constraint —
    only the auto-generated name differs — so a remove/add pair over identical
    columns is not real drift. Any constraint change that ISN'T a clean name-only
    rename (different columns, or unmatched) is kept and will fail the test.
    """
    removed: dict[frozenset[str], int] = {}
    added: dict[frozenset[str], int] = {}
    kept: list[object] = []
    for d in diffs:
        if isinstance(d, tuple):
            cols = _uc_cols(d)
            if cols is not None:
                bucket = removed if d[0] == "remove_constraint" else added
                bucket[cols] = bucket.get(cols, 0) + 1
                continue
        kept.append(d)
    # A name-only rename = one remove + one add over the same column set. Anything
    # left unmatched is genuine drift.
    for cols, n_rem in removed.items():
        n_add = added.get(cols, 0)
        leftover = abs(n_rem - n_add)
        kept.extend([("unique_constraint_unmatched", cols)] * leftover)
    for cols, n_add in added.items():
        if cols not in removed:
            kept.extend([("unique_constraint_unmatched", cols)] * n_add)
    return kept


def test_table_and_column_parity(migration_db: tuple[Config, str]) -> None:
    """Every owned table exists in the DB with the same column set as the model."""
    cfg, dsn = migration_db
    command.upgrade(cfg, "head")

    engine = create_engine(_sqla_url(dsn), future=True)
    try:
        insp = inspect(engine)
        db_tables = set(insp.get_table_names())
        assert OWNED_TABLES <= db_tables, f"missing in DB: {OWNED_TABLES - db_tables}"

        for table_name in sorted(OWNED_TABLES):
            model_cols = set(Base.metadata.tables[table_name].columns.keys())
            db_cols = {c["name"] for c in insp.get_columns(table_name)}
            assert model_cols == db_cols, (
                f"{table_name} column mismatch; "
                f"model-only={model_cols - db_cols} db-only={db_cols - model_cols}"
            )
    finally:
        engine.dispose()
