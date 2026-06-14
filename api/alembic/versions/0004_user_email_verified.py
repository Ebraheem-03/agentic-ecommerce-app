"""users.email_verified column (auth login gate, US-E4-04)

Revision ID: 0004_email_verified
Revises: 0003_embeddings
Create Date: 2026-06-17

Additive, non-breaking: adds ``users.email_verified boolean NOT NULL DEFAULT false``
so the ``/auth/login`` handler can deny (403 forbidden) accounts that have not yet
verified their email (ADR-0023). Default ``false`` keeps a re-applied schema
deterministic; auth-backed seeding flips the seeded personas to ``true``.

Reversible: upgrade adds the column, downgrade drops it (no data migration needed).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_email_verified"
down_revision: str | None = "0003_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users "
        "ADD COLUMN email_verified boolean NOT NULL DEFAULT false;"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS email_verified;")
