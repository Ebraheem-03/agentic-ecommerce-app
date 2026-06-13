"""Orders, order items, and test-mode payments.

Single multi-store order with per-item snapshots (title/options/store name/unit
price frozen at checkout) — matches the ORM ``order_items`` snapshot columns and the
ERD ruling. Payment is TEST-MODE: a placeholder intent/confirm pair that maps to the
``payments`` table + ``payment_status`` enum; no real provider is called.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import AddressIn
from app.schemas.enums import FulfilStatus, OrderStatus, PaymentStatus
from app.schemas.envelope import CamelModel


class CheckoutRequest(CamelModel):
    """POST /orders — convert the open cart into an order.

    ``idempotency_key`` can also be supplied via the ``Idempotency-Key`` header
    (preferred); the body field is the documented fallback. Replays return the
    same order rather than creating a second one.
    """

    ship_address: AddressIn
    idempotency_key: str | None = Field(
        default=None,
        max_length=200,
        description="Client-generated key to make checkout idempotent (or use header).",
    )


class OrderItemOut(CamelModel):
    """A frozen order line (snapshot fields are immutable post-checkout)."""

    id: str
    variant_id: str | None = None
    title_snapshot: str
    options_snapshot: dict[str, object] = Field(default_factory=dict)
    store_name_snapshot: str
    unit_price_minor: int = Field(ge=0)
    qty: int = Field(ge=1)
    fulfil_status: FulfilStatus


class PaymentOut(CamelModel):
    """A test-mode payment record."""

    id: str
    status: PaymentStatus
    provider_ref: str | None = None
    amount_minor: int = Field(ge=0)
    currency: str = "USD"
    created_at: datetime


class PaymentIntentOut(CamelModel):
    """POST /orders/{id}/payment-intent — mock intent the client 'confirms'."""

    payment_id: str
    client_secret: str = Field(description="Mock secret; test-mode only, not a real PSP.")
    status: PaymentStatus
    amount_minor: int = Field(ge=0)
    currency: str = "USD"


class PaymentConfirmRequest(CamelModel):
    """POST /orders/{id}/payment-confirm — confirm the mock intent.

    ``outcome`` lets QA/E2E deterministically drive success vs decline in test-mode.
    """

    payment_id: str
    outcome: PaymentStatus = Field(
        default=PaymentStatus.captured,
        description="Test-mode hint: 'captured' (success) or 'failed' (decline).",
    )


class OrderSummary(CamelModel):
    """Order as shown in 'my orders' list."""

    id: str
    order_number: str
    status: OrderStatus
    total_minor: int = Field(ge=0)
    currency: str = "USD"
    item_count: int = Field(ge=0)
    placed_at: datetime


class OrderDetail(OrderSummary):
    """Full order detail + status timeline source."""

    subtotal_minor: int = Field(ge=0)
    shipping_minor: int = Field(ge=0)
    tax_minor: int = Field(ge=0)
    ship_address: dict[str, object] | None = None
    items: list[OrderItemOut]
    payments: list[PaymentOut]
    updated_at: datetime
