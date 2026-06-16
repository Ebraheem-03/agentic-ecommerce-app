"""Semantic cache table — non-personalized LLM response cache (US-E5-09, ADR-0034 §2).

Mirrors the schema authored by migration ``0007_semantic_cache`` (the source of truth).
The vector dimension is read from ``settings.embed_dim`` — NEVER hardcoded — so the ORM
column agrees with whatever dimension the live table was migrated at (the same 768 as the
``embeddings`` table). See ``app.agent.cache`` for the lookup/store policy.
"""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import DateTime, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.db.base import Base
from app.db.models._shared import created_at_col, uuid_pk


class SemanticCacheEntry(Base):
    __tablename__ = "semantic_cache"

    id: Mapped[str] = uuid_pk()
    # Namespace fields — a hit must match ALL of these (ADR-0034 §2 key composition).
    node_type: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    embed_provider: Mapped[str] = mapped_column(Text, nullable=False)
    embed_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    # Store scope (policy entries only; classifier entries are global -> NULL).
    store_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))

    norm_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    # Dimension from settings — agrees with the migrated vector(EMBED_DIM) column.
    query_embedding: Mapped[list[float]] = mapped_column(
        Vector(settings.embed_dim), nullable=False
    )
    response: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    source_ids: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    content_version: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    created_at: Mapped[datetime] = created_at_col()
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        Index(
            "ix_semantic_cache_namespace",
            "node_type",
            "provider",
            "model",
            "embed_provider",
            "embed_dim",
            "store_id",
            "norm_prompt",
        ),
        # HNSW cosine index — mirrors migration 0007. Declared so autogenerate sees it.
        Index(
            "ix_semantic_cache_embedding_hnsw",
            "query_embedding",
            postgresql_using="hnsw",
            postgresql_ops={"query_embedding": "vector_cosine_ops"},
        ),
        Index("ix_semantic_cache_expires_at", "expires_at"),
    )
