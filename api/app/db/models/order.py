"""Orders, order items, payments."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models._shared import (
    created_at_col,
    pg_enum,
    updated_at_col,
    uuid_pk,
)

if TYPE_CHECKING:
    from app.db.models.returns import Return


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = uuid_pk()
    order_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    cart_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("carts.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(
        pg_enum("order_status"), nullable=False, server_default=text("'placed'")
    )
    subtotal_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    shipping_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    tax_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    total_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    currency: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'USD'")
    )
    ship_address: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    placed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = updated_at_col()

    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    payments: Mapped[list[Payment]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    returns: Mapped[list[Return]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_orders_user_id", "user_id"),)


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = uuid_pk()
    order_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("variants.id", ondelete="SET NULL")
    )
    title_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    options_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    store_name_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    fulfil_status: Mapped[str] = mapped_column(
        pg_enum("fulfil_status"), nullable=False, server_default=text("'pending'")
    )

    order: Mapped[Order] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_order_items_qty_pos"),
        Index("ix_order_items_order_id", "order_id"),
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = uuid_pk()
    order_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        pg_enum("payment_status"), nullable=False, server_default=text("'pending'")
    )
    provider_ref: Mapped[str | None] = mapped_column(Text)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'USD'")
    )
    created_at: Mapped[datetime] = created_at_col()

    order: Mapped[Order] = relationship(back_populates="payments")

    __table_args__ = (Index("ix_payments_order_id", "order_id"),)
