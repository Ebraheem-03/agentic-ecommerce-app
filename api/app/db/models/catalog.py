"""Stores and catalog: stores, products, reviews, variants, images, inventory."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
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
from app.db.models.user import User

if TYPE_CHECKING:
    from app.db.models.policy import Policy


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[str] = uuid_pk()
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    location: Mapped[str | None] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        pg_enum("store_status"), nullable=False, server_default=text("'draft'")
    )
    payout_pct: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("88")
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    owner: Mapped[User] = relationship(back_populates="stores")
    products: Mapped[list[Product]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )
    policies: Mapped[list[Policy]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_stores_owner_id", "owner_id"),)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = uuid_pk()
    store_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    category: Mapped[str | None] = mapped_column(Text)
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(
        pg_enum("product_status"), nullable=False, server_default=text("'draft'")
    )
    # DERIVED rollups of reviews — recomputed app-side on review write.
    rating_avg: Mapped[float | None] = mapped_column(Numeric(2, 1))
    rating_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    store: Mapped[Store] = relationship(back_populates="products")
    reviews: Mapped[list[Review]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    variants: Mapped[list[Variant]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    images: Mapped[list[ProductImage]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_products_store_id", "store_id"),)


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = uuid_pk()
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = created_at_col()

    product: Mapped[Product] = relationship(back_populates="reviews")

    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating_range"),
        UniqueConstraint(
            "product_id", "user_id", name="uq_reviews_product_id_user_id"
        ),
        Index("ix_reviews_product_id", "product_id"),
    )


class Variant(Base):
    __tablename__ = "variants"

    id: Mapped[str] = uuid_pk()
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    sku: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    options: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'USD'")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    product: Mapped[Product] = relationship(back_populates="variants")
    inventory: Mapped[Inventory | None] = relationship(
        back_populates="variant", cascade="all, delete-orphan", uselist=False
    )

    __table_args__ = (
        CheckConstraint("price_minor >= 0", name="ck_variants_price_nonneg"),
        Index("ix_variants_product_id", "product_id"),
    )


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[str] = uuid_pk()
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("variants.id", ondelete="SET NULL")
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    alt: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    position: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    product: Mapped[Product] = relationship(back_populates="images")

    __table_args__ = (Index("ix_product_images_product_id", "product_id"),)


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[str] = uuid_pk()
    variant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("variants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    qty_on_hand: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    qty_reserved: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    restock_eta_days: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = updated_at_col()

    variant: Mapped[Variant] = relationship(back_populates="inventory")

    __table_args__ = (
        CheckConstraint(
            "qty_on_hand >= 0 AND qty_reserved >= 0", name="ck_inventory_qty_nonneg"
        ),
    )
