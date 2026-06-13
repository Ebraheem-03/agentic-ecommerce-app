"""Seller surfaces: store onboarding, list-product, merchandising nudge, fulfilment.

Implied by the seller-dashboard screen + J-SEL-01..05. Nudge generation is agent-
backed (Echo); the publish/accept path is audited (agent_actions). These are thin
contract DTOs — business logic lands later.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.enums import FulfilStatus, StoreStatus
from app.schemas.envelope import CamelModel


class StoreOnboardRequest(CamelModel):
    """POST /seller/store — create/complete the seller's store profile."""

    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9-]+$")
    location: str | None = Field(default=None, max_length=200)
    bio: str | None = Field(default=None, max_length=4000)


class VariantCreate(CamelModel):
    """A variant within a list-product request."""

    sku: str = Field(min_length=1, max_length=120)
    options: dict[str, object] = Field(default_factory=dict)
    price_minor: int = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    qty_on_hand: int = Field(default=0, ge=0)


class ProductCreate(CamelModel):
    """POST /seller/products — list a product (J-SEL-02)."""

    title: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9-]+$")
    description: str = Field(default="", max_length=8000)
    category: str | None = Field(default=None, max_length=120)
    attributes: dict[str, object] = Field(default_factory=dict)
    variants: list[VariantCreate] = Field(min_length=1)


class StoreOut(CamelModel):
    """The seller's store."""

    id: str
    name: str
    slug: str
    location: str | None = None
    bio: str | None = None
    status: StoreStatus
    payout_pct: int
    created_at: datetime


class NudgeOut(CamelModel):
    """A merchandising/pricing nudge (agent-generated, grounded in catalog data).

    Backs ``seller-dashboard-nudge`` + ``-nudge-reason`` + ``-nudge-accept``.
    """

    id: str
    product_id: str
    headline: str
    reason: str = Field(description="Grounded rationale — references real catalog data.")
    suggested_change: dict[str, object] = Field(default_factory=dict)


class NudgeAcceptRequest(CamelModel):
    """POST /seller/nudges/{id}/accept — apply the nudge (audited, reversible)."""

    idempotency_key: str | None = Field(default=None, max_length=200)


class FulfilRequest(CamelModel):
    """PATCH /seller/order-items/{id}/fulfil — mark a line fulfilled/cancelled."""

    fulfil_status: FulfilStatus
