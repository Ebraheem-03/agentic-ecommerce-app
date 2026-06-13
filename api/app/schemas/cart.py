"""Cart: the single open cart per user and its items.

Honors schema invariants: one OPEN cart per user (partial unique), cart_items
``qty > 0`` CHECK, and unique (cart_id, variant_id). Adding an existing variant is
an upsert of qty at the route level; the API enforces qty > 0 here.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.enums import CartStatus
from app.schemas.envelope import CamelModel


class CartItemAdd(CamelModel):
    """POST /cart/items — add (or increment) a variant in the open cart."""

    variant_id: str
    qty: int = Field(ge=1, le=999, description="Quantity to add; must be positive.")


class CartItemUpdate(CamelModel):
    """PATCH /cart/items/{item_id} — set absolute quantity (qty>0; 0 => use DELETE)."""

    qty: int = Field(ge=1, le=999)


class CartItemOut(CamelModel):
    """A line item with denormalized display fields + live stock signal."""

    id: str
    variant_id: str
    product_id: str
    title: str
    sku: str
    options: dict[str, object] = Field(default_factory=dict)
    unit_price_minor: int = Field(ge=0)
    currency: str = "USD"
    qty: int = Field(ge=1)
    line_total_minor: int = Field(ge=0)
    in_stock: bool = True
    added_at: datetime


class CartOut(CamelModel):
    """The current cart with computed subtotal."""

    id: str
    status: CartStatus
    items: list[CartItemOut]
    subtotal_minor: int = Field(ge=0)
    currency: str = "USD"
    item_count: int = Field(ge=0, description="Sum of line quantities.")
    updated_at: datetime
