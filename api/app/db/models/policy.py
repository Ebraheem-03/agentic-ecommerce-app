"""Policies — the RAG source the support agent retrieves over."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models._shared import NOW_DEFAULT, pg_enum, updated_at_col, uuid_pk

if TYPE_CHECKING:
    from app.db.models.catalog import Store


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[str] = uuid_pk()
    store_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("stores.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(pg_enum("policy_kind"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=NOW_DEFAULT
    )
    updated_at: Mapped[datetime] = updated_at_col()

    store: Mapped[Store | None] = relationship(back_populates="policies")

    __table_args__ = (Index("ix_policies_store_id", "store_id"),)
