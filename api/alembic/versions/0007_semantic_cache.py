"""semantic_cache table — non-personalized LLM response cache (US-E5-09, ADR-0034 §2)

Revision ID: 0007_semantic_cache
Revises: 0006_idempotency_keys
Create Date: 2026-06-25

A pgvector-backed cache so repeated/similar NON-PERSONALIZED prompts (intent
classification + grounded policy-RAG answers) skip the LLM round-trip. The cache is an
OPTIMIZATION: a lookup miss/failure degrades to a live LLM call, never an error.

Key composition (ADR-0034 §2): an entry is matched within a NAMESPACE of
``(provider, model, node_type, embed_provider, embed_dim [, store_id])`` — a provider/dim
swap must never serve vectors from a different space, ``node_type`` namespacing means a
shopping prompt can never resolve a support entry, and policy entries are store-scoped so
a store-A shopper can't be served a store-B policy answer. Within a namespace, a hit is a
cosine ``query_embedding`` neighbour at/above the configured threshold (real embedder), or
an EXACT ``norm_prompt`` match under the stub embedder.

The ``query_embedding`` column is ``vector(EMBED_DIM)`` — the SAME dimension as the
``embeddings`` table (768; this migration does NOT change ``EMBED_DIM``). The HNSW cosine
index mirrors migration 0003.

Invalidation (ADR-0034 §2): content-version is primary (``source_ids`` + the grounding
rows' version captured in ``content_version``), TTL is the backstop (``expires_at``). A
store/policy edit busts stale policy entries; ``expires_at`` caps everything.

Reversible: upgrade creates the table + indexes; downgrade drops it. Additive — no
existing table is touched.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from app.core.config import settings

# revision identifiers, used by Alembic.
revision: str = "0007_semantic_cache"
down_revision: str | None = "0006_idempotency_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    dim = settings.embed_dim
    op.execute(
        f"""
        CREATE TABLE semantic_cache (
            id              uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
            node_type       text NOT NULL,
            provider        text NOT NULL,
            model           text NOT NULL,
            embed_provider  text NOT NULL,
            embed_dim       integer NOT NULL,
            store_id        uuid,
            norm_prompt     text NOT NULL,
            query_embedding vector({dim}) NOT NULL,
            response        jsonb NOT NULL,
            source_ids      text[] NOT NULL DEFAULT '{{}}',
            content_version text NOT NULL DEFAULT '',
            created_at      timestamptz NOT NULL DEFAULT now(),
            expires_at      timestamptz NOT NULL
        );
        """
    )
    # Namespace + exact-match lookup (the stub-embedder tier matches on norm_prompt within
    # the namespace). Not UNIQUE: the same prompt may be re-stored after invalidation; the
    # lookup orders by created_at DESC and prunes stale rows.
    op.execute(
        "CREATE INDEX ix_semantic_cache_namespace "
        "ON semantic_cache "
        "(node_type, provider, model, embed_provider, embed_dim, store_id, norm_prompt);"
    )
    # HNSW cosine ANN index for the real-embedder similarity tier (mirrors migration 0003).
    op.execute(
        "CREATE INDEX ix_semantic_cache_embedding_hnsw "
        "ON semantic_cache USING hnsw (query_embedding vector_cosine_ops);"
    )
    # TTL sweep helper.
    op.execute(
        "CREATE INDEX ix_semantic_cache_expires_at ON semantic_cache (expires_at);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS semantic_cache CASCADE;")
