"""The single polymorphic, chunked pgvector embeddings table.

The vector dimension is read from ``settings.embed_dim`` (env ``EMBED_DIM``) — NEVER
hardcoded. Echo owns the final dimension; re-sizing is one down/up on migration 0003.
The ORM column must agree with whatever dimension the live table was migrated at.
"""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.db.base import Base
from app.db.models._shared import created_at_col, pg_enum, uuid_pk


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[str] = uuid_pk()
    source_type: Mapped[str] = mapped_column(
        pg_enum("embedding_source"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    # Dimension from settings — agrees with the migrated vector(EMBED_DIM) column.
    embedding: Mapped[list[float]] = mapped_column(
        Vector(settings.embed_dim), nullable=False
    )
    model: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        UniqueConstraint(
            "source_type", "source_id", "chunk_index", name="uq_embeddings_source"
        ),
        Index("ix_embeddings_source", "source_type", "source_id"),
        # HNSW cosine index — mirrors migration 0003. Declared so autogenerate sees
        # it; the migration already created it on the live DB.
        Index(
            "ix_embeddings_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
