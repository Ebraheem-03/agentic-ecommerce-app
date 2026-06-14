"""idempotency_keys table (checkout + payment idempotency, US-E4-10)

Revision ID: 0006_idempotency_keys
Revises: 0005_product_search
Create Date: 2026-06-14

Adds a single ``idempotency_keys`` table so state-mutating, money-touching routes
(checkout, payment-intent, payment-confirm — contract-v0 §1.3) are replay-safe: a
repeat of the same ``Idempotency-Key`` returns the ORIGINAL stored result instead of
creating a second order/payment.

The natural key is ``(user_id, key, endpoint)``:
  * ``user_id``  — scopes a key to its owner so two users can't collide / leak.
  * ``key``      — the client-generated ``Idempotency-Key`` header (or body fallback).
  * ``endpoint`` — a stable route tag (e.g. ``orders:checkout``) so the same key on
    two different endpoints stays independent.

``response_json`` stores the serialized success body so a replay can re-emit it
verbatim without re-running the handler. ``status_code`` records the original HTTP
status. Rows are scoped by user (``ON DELETE CASCADE``) so they vanish with the user.

Reversible: upgrade creates the table + its unique key; downgrade drops it. Additive
and non-breaking — no existing table is touched.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_idempotency_keys"
down_revision: str | None = "0005_product_search"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE idempotency_keys (
            id            uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
            user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            key           text NOT NULL,
            endpoint      text NOT NULL,
            status_code   integer NOT NULL,
            response_json jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at    timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_idempotency_user_key_endpoint
                UNIQUE (user_id, key, endpoint)
        );
        """
    )
    op.execute(
        "CREATE INDEX ix_idempotency_keys_user_id ON idempotency_keys (user_id);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS idempotency_keys;")
