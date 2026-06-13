"""Catalog: stores, products, variants, images, reviews."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.enums import ProductStatus, StoreStatus
from app.schemas.envelope import CamelModel


class StoreSummary(CamelModel):
    """Store as shown on product cards / detail headers."""

    id: str
    name: str
    slug: str
    location: str | None = None
    status: StoreStatus


class StoreDetail(StoreSummary):
    """Full store detail (storefront page)."""

    bio: str | None = None
    created_at: datetime


class VariantOut(CamelModel):
    """A purchasable variant with price + live stock signal."""

    id: str
    sku: str
    options: dict[str, object] = Field(default_factory=dict)
    price_minor: int = Field(ge=0)
    currency: str = "USD"
    is_active: bool = True
    # Derived from inventory (qty_on_hand - qty_reserved). Boolean keeps stock
    # levels private while still driving the out-of-stock UI state.
    in_stock: bool = True
    restock_eta_days: int | None = None


class ProductImageOut(CamelModel):
    """A product image."""

    id: str
    url: str
    alt: str = ""
    position: int = 0
    variant_id: str | None = None


class ReviewOut(CamelModel):
    """A single product review."""

    id: str
    product_id: str
    user_id: str
    rating: int = Field(ge=1, le=5)
    title: str | None = None
    body: str = ""
    created_at: datetime


class ReviewCreate(CamelModel):
    """POST /products/{id}/reviews — one per (product, user)."""

    rating: int = Field(ge=1, le=5)
    title: str | None = Field(default=None, max_length=200)
    body: str = Field(default="", max_length=4000)


class ProductSummary(CamelModel):
    """Product as shown in lists / search results / recommendation cards."""

    id: str
    title: str
    slug: str
    category: str | None = None
    status: ProductStatus
    store: StoreSummary
    # Cheapest active variant price, for list/card display.
    from_price_minor: int | None = Field(default=None, ge=0)
    currency: str = "USD"
    primary_image: ProductImageOut | None = None
    # DERIVED rollups (recomputed on review write); rating_avg null until first review.
    rating_avg: float | None = Field(default=None, ge=0, le=5)
    rating_count: int = 0


class ProductDetail(ProductSummary):
    """Full product detail page payload."""

    description: str = ""
    attributes: dict[str, object] = Field(default_factory=dict)
    variants: list[VariantOut]
    images: list[ProductImageOut]
    created_at: datetime
    updated_at: datetime
