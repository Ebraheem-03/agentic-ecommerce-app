"""Returns and return items."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
from app.db.models._shared import created_at_col, pg_enum, uuid_pk
from app.db.models.order import Order


class Return(Base):
    __tablename__ = "returns"

    id: Mapped[str] = uuid_pk()
    order_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        pg_enum("return_status"), nullable=False, server_default=text("'requested'")
    )
    reason_code: Mapped[str] = mapped_column(pg_enum("return_reason"), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    within_window: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    approved_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    order: Mapped[Order] = relationship(back_populates="returns")
    items: Mapped[list[ReturnItem]] = relationship(
        back_populates="return_", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_returns_order_id", "order_id"),)


class ReturnItem(Base):
    __tablename__ = "return_items"

    id: Mapped[str] = uuid_pk()
    return_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("returns.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_item_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("order_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False)

    return_: Mapped[Return] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_return_items_qty_pos"),
        Index("ix_return_items_return_id", "return_id"),
    )
