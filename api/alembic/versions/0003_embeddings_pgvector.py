"""embeddings table + HNSW cosine index (dimension-driven)

Revision ID: 0003_embeddings
Revises: 0002_core_schema
Create Date: 2026-06-12

Isolated migration for the single polymorphic, chunked pgvector table. Kept
separate so that re-sizing the vector to a different embedding model is exactly
one down/up step (downgrade 0003 -> set EMBED_DIM -> upgrade head).

ECHO COORDINATION POINT: the vector dimension comes from `settings.embed_dim`
(env `EMBED_DIM`, default 768 = Gemini text-embedding-004). The HNSW cosine index
is created at that same dimension. pgvector 0.8.x in the pgvector/pgvector:pg16
image ships HNSW; if a future image lacks it, swap the index for IVFFlat.
See docs/decisions/0018-uuidv7-and-pgvector-dim.md.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from app.core.config import settings

# revision identifiers, used by Alembic.
revision: str = "0003_embeddings"
down_revision: str | None = "0002_core_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    dim = settings.embed_dim
    op.execute(
        f"""
        CREATE TABLE embeddings (
            id          uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
            source_type embedding_source NOT NULL,
            source_id   uuid NOT NULL,
            chunk_text  text NOT NULL,
            chunk_index integer NOT NULL DEFAULT 0,
            embedding   vector({dim}) NOT NULL,
            model       text NOT NULL,
            created_at  timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_embeddings_source UNIQUE (source_type, source_id, chunk_index)
        );
        """
    )
    # Filter embeddings by what they belong to (product vs policy chunk).
    op.execute("CREATE INDEX ix_embeddings_source ON embeddings (source_type, source_id);")
    # HNSW cosine ANN index for retrieval. m / ef_construction left at pgvector
    # defaults — fine for the v0 catalog size.
    op.execute(
        "CREATE INDEX ix_embeddings_embedding_hnsw "
        "ON embeddings USING hnsw (embedding vector_cosine_ops);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS embeddings CASCADE;")
