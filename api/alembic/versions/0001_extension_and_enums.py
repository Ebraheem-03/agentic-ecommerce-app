"""pgvector extension + all native enum types

Revision ID: 0001_ext_enums
Revises:
Create Date: 2026-06-12

First migration: makes the DB ready for the schema. Enables pgvector (idempotent,
so the schema applies even on a DB whose init script never ran) and declares every
closed-set Postgres ENUM the schema depends on. Enums are created here so later
table migrations can reference them by name.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_ext_enums"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# name -> ordered list of allowed values
ENUMS: dict[str, list[str]] = {
    "user_role": ["buyer", "seller", "support", "admin"],
    "store_status": ["draft", "active", "suspended"],
    "product_status": ["draft", "active", "archived"],
    "cart_status": ["open", "converted", "abandoned"],
    "order_status": ["placed", "packed", "shipped", "delivered", "cancelled"],
    "fulfil_status": ["pending", "fulfilled", "cancelled"],
    "payment_status": ["pending", "authorized", "captured", "failed", "refunded"],
    "return_status": ["requested", "approved", "rejected", "hitl_pending", "refunded"],
    "return_reason": [
        "damaged",
        "not_as_described",
        "wrong_item",
        "no_longer_needed",
        "arrived_late",
        "other",
    ],
    "policy_kind": ["returns", "shipping", "payments", "care", "platform"],
    "conversation_surface": ["buyer", "support", "seller"],
    "message_role": ["user", "assistant", "system", "tool"],
    "agent_outcome": ["applied", "refused", "hitl_deferred"],
    "embedding_source": ["product", "policy"],
}


def upgrade() -> None:
    # pgvector — idempotent so a fresh DB without the init script still works.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    for name, values in ENUMS.items():
        labels = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {name} AS ENUM ({labels});")


def downgrade() -> None:
    for name in reversed(list(ENUMS)):
        op.execute(f"DROP TYPE IF EXISTS {name};")
    # Leave the vector extension in place on downgrade — other DBs/objects may use
    # it, and dropping an extension that init.sql also manages is surprising.
