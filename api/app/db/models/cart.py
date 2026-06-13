"""Carts and cart items."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models._shared import (
    NOW_DEFAULT,
    created_at_col,
    pg_enum,
    updated_at_col,
    uuid_pk,
)


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    anon_token: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        pg_enum("cart_status"), nullable=False, server_default=text("'open'")
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    items: Mapped[list[CartItem]] = relationship(
        back_populates="cart", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # At most one OPEN cart per user (partial unique).
        Index(
            "uq_carts_one_open_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'open' AND user_id IS NOT NULL"),
        ),
    )


class CartItem(Base):
    __tablename__ = "cart_items"

    id: Mapped[str] = uuid_pk()
    cart_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("carts.id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("variants.id", ondelete="CASCADE"),
        nullable=False,
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=NOW_DEFAULT
    )

    cart: Mapped[Cart] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_cart_items_qty_pos"),
        UniqueConstraint(
            "cart_id", "variant_id", name="uq_cart_items_cart_id_variant_id"
        ),
    )
