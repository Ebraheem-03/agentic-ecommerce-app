"""Alembic migration contract (US-QA-D04).

Turns Sable's one-off manual upgrade->downgrade->upgrade proof into a repeatable,
CI-runnable contract. Three scenarios, each asserted against the live catalog
(information_schema / pg_type / pg_proc / pg_indexes / pg_constraint) rather than
trusting Alembic's exit code:

1. clean_create  — empty DB -> `upgrade head` -> the expected object inventory.
2. rollback      — `downgrade base` cleanly reverses; idempotent round-trip back to head.
3. (reset is the shell harness api/scripts/db_reset.sh, smoke-checked here for guards.)

Object expectations are named, not just counted, so a brittle count can't pass while
the wrong objects exist. Mirrors docs/data/erd.md (APPROVED 2026-06-12). See ADR-0019
and docs/qa/db-migration-test-plan.md.
"""

from __future__ import annotations

from alembic.config import Config
from psycopg import Connection

from alembic import command

from .conftest import open_conn

# ---- expected object inventory (source of truth: erd.md + the 3 migrations) -----

# 20 from 0002_core_schema + `embeddings` from 0003 = 21 app tables (excl. alembic_version).
EXPECTED_TABLES: frozenset[str] = frozenset(
    {
        "users",
        "sessions",
        "addresses",
        "stores",
        "products",
        "reviews",
        "variants",
        "product_images",
        "inventory",
        "carts",
        "cart_items",
        "orders",
        "order_items",
        "payments",
        "returns",
        "return_items",
        "policies",
        "conversations",
        "messages",
        "agent_actions",
        "embeddings",
    }
)

# 14 native enums declared in 0001_extension_and_enums.
EXPECTED_ENUMS: frozenset[str] = frozenset(
    {
        "user_role",
        "store_status",
        "product_status",
        "cart_status",
        "order_status",
        "fulfil_status",
        "payment_status",
        "return_status",
        "return_reason",
        "policy_kind",
        "conversation_surface",
        "message_role",
        "agent_outcome",
        "embedding_source",
    }
)


# ---- catalog introspection helpers ----------------------------------------------


def _app_tables(conn: Connection) -> set[str]:
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
        "AND table_name <> 'alembic_version'"
    ).fetchall()
    return {r[0] for r in rows}


def _enum_types(conn: Connection) -> set[str]:
    rows = conn.execute("SELECT typname FROM pg_type WHERE typtype = 'e'").fetchall()
    return {r[0] for r in rows}


def _scalar(conn: Connection, sql: str, *params: object) -> object:
    row = conn.execute(sql, params or None).fetchone()
    assert row is not None
    return row[0]


# ---- scenario 1: clean create ---------------------------------------------------


def test_clean_create(migration_db: tuple[Config, str]) -> None:
    """From an empty DB, `upgrade head` produces exactly the expected objects."""
    cfg, dsn = migration_db

    with open_conn(dsn) as conn:
        # Sanity: the throwaway DB really is empty before we migrate.
        assert _app_tables(conn) == set()
        assert _enum_types(conn) == set()

    command.upgrade(cfg, "head")

    with open_conn(dsn) as conn:
        # --- tables: named, not just counted ---
        tables = _app_tables(conn)
        assert tables == EXPECTED_TABLES, (
            f"table set mismatch; missing={EXPECTED_TABLES - tables} "
            f"unexpected={tables - EXPECTED_TABLES}"
        )
        assert len(tables) == 21

        # --- 14 native enums ---
        enums = _enum_types(conn)
        assert enums == EXPECTED_ENUMS, (
            f"enum set mismatch; missing={EXPECTED_ENUMS - enums} "
            f"unexpected={enums - EXPECTED_ENUMS}"
        )

        # --- pgvector extension present ---
        assert _scalar(conn, "SELECT count(*) FROM pg_extension WHERE extname = 'vector'") == 1

        # --- uuid_generate_v7() helper installed (UUIDv7 server-side default) ---
        assert _scalar(conn, "SELECT count(*) FROM pg_proc WHERE proname = 'uuid_generate_v7'") == 1

        # --- HNSW cosine index on embeddings.embedding ---
        assert (
            _scalar(
                conn,
                "SELECT count(*) FROM pg_indexes "
                "WHERE tablename = 'embeddings' AND indexname = 'ix_embeddings_embedding_hnsw'",
            )
            == 1
        )
        # ...and it is genuinely an HNSW index (not a renamed btree).
        assert (
            _scalar(
                conn,
                "SELECT am.amname FROM pg_class c "
                "JOIN pg_am am ON am.oid = c.relam "
                "WHERE c.relname = 'ix_embeddings_embedding_hnsw'",
            )
            == "hnsw"
        )

        # --- key constraints (a representative, load-bearing few) ---
        # partial-unique: at most one OPEN cart per user
        assert (
            _scalar(
                conn,
                "SELECT count(*) FROM pg_indexes "
                "WHERE indexname = 'uq_carts_one_open_per_user'",
            )
            == 1
        )
        # reviews rating CHECK (1..5)
        assert (
            _scalar(
                conn,
                "SELECT count(*) FROM pg_constraint WHERE conname = 'ck_reviews_rating_range'",
            )
            == 1
        )
        # inventory.variant_id UNIQUE (one stock row per variant)
        assert (
            _scalar(
                conn,
                "SELECT count(*) FROM pg_constraint c "
                "WHERE c.conrelid = 'inventory'::regclass AND c.contype = 'u'",
            )
            == 1
        )


# ---- scenario 2: rollback + idempotent round-trip -------------------------------


def test_rollback_to_base_then_roundtrip(migration_db: tuple[Config, str]) -> None:
    """`downgrade base` cleanly reverses; re-`upgrade head` is idempotent."""
    cfg, dsn = migration_db

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    with open_conn(dsn) as conn:
        # 0 app tables, 0 enums, uuid fn gone.
        assert _app_tables(conn) == set()
        assert _enum_types(conn) == set()
        assert _scalar(conn, "SELECT count(*) FROM pg_proc WHERE proname = 'uuid_generate_v7'") == 0

        # Only alembic_version remains, and it holds no pinned revision.
        assert (
            _scalar(
                conn,
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'alembic_version'",
            )
            == 1
        )
        assert _scalar(conn, "SELECT count(*) FROM alembic_version") == 0

        # DOCUMENTED EXCEPTION: 0001's downgrade intentionally leaves the `vector`
        # extension in place (dropping an extension an init script also manages is
        # surprising and can break sibling objects). This is a deliberate design
        # choice, asserted here so a future "drop it too" change is a conscious one.
        assert _scalar(conn, "SELECT count(*) FROM pg_extension WHERE extname = 'vector'") == 1

    # Idempotent round-trip: head again returns the full inventory.
    command.upgrade(cfg, "head")
    with open_conn(dsn) as conn:
        assert _app_tables(conn) == EXPECTED_TABLES
        assert _enum_types(conn) == EXPECTED_ENUMS
        assert _scalar(conn, "SELECT version_num FROM alembic_version") == "0003_embeddings"
