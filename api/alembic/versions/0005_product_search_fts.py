"""products full-text search column + GIN index (keyword retrieval, US-E4-07)

Revision ID: 0005_product_search
Revises: 0004_email_verified
Create Date: 2026-06-18

Keyword search (contract-v0 Decision-4) is the LIVE retrieval path today; pgvector
semantic retrieval is deferred to Echo (Week-4) and drops in behind the SAME response
shape with no contract change. To make keyword search genuinely relevant we back it
with Postgres full-text search rather than naive ILIKE:

  * ``products.search_tsv`` — a STORED generated ``tsvector`` over the searchable text
    (title weighted ``A``, category ``B``, description ``C``). Generated, so it stays
    in sync with the row automatically; no trigger or app-side maintenance.
  * ``ix_products_search_tsv`` — a GIN index on that column so ``@@`` matching with
    ``ts_rank`` ordering stays fast as the catalog grows.

The retrieval service queries with ``websearch_to_tsquery('english', :q)`` and orders
by ``ts_rank(search_tsv, query)`` (the per-result ``score``). See ADR-0027.

Reversible: downgrade drops the index then the generated column (no data migration).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_product_search"
down_revision: str | None = "0004_email_verified"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # STORED generated tsvector: title (A) > category (B) > description (C). COALESCE
    # because category is nullable; description defaults to '' but COALESCE is cheap
    # insurance. Immutable expression as required for a generated column.
    op.execute(
        """
        ALTER TABLE products
        ADD COLUMN search_tsv tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(category, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(description, '')), 'C')
        ) STORED;
        """
    )
    op.execute(
        "CREATE INDEX ix_products_search_tsv ON products USING gin (search_tsv);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_products_search_tsv;")
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS search_tsv;")
