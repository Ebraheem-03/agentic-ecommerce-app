"""Order + test-mode payment + returns routes (contract draft)."""

from __future__ import annotations

from fastapi import APIRouter, Header, Query, status

from app.api._contract import ERROR_RESPONSES, stub
from app.schemas.envelope import Envelope, ListEnvelope
from app.schemas.order import (
    CheckoutRequest,
    OrderDetail,
    OrderSummary,
    PaymentConfirmRequest,
    PaymentIntentOut,
    PaymentOut,
)
from app.schemas.returns import ReturnCreate, ReturnOut

router = APIRouter(prefix="/orders", tags=["orders"], responses=ERROR_RESPONSES)


@router.post(
    "",
    response_model=Envelope[OrderDetail],
    status_code=status.HTTP_201_CREATED,
    summary="Checkout: create an order from the open cart (idempotent)",
)
def create_order(
    body: CheckoutRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Envelope[OrderDetail]:
    """Convert the open cart into an order. Replays of the key return the same order.

    ``empty_cart`` if the cart has no items; ``out_of_stock`` on inventory shortfall.
    (J-BUY-04)
    """
    stub()


@router.get("", response_model=ListEnvelope[OrderSummary], summary="List my orders")
def list_orders(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> ListEnvelope[OrderSummary]:
    """List the caller's orders, newest first."""
    stub()


@router.get(
    "/{order_id}",
    response_model=Envelope[OrderDetail],
    summary="Get an order (detail + status)",
)
def get_order(order_id: str) -> Envelope[OrderDetail]:
    """Order detail incl. status timeline source + items. (J-BUY-05)"""
    stub()


@router.post(
    "/{order_id}/payment-intent",
    response_model=Envelope[PaymentIntentOut],
    status_code=status.HTTP_201_CREATED,
    summary="Create a TEST-MODE payment intent",
)
def create_payment_intent(
    order_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Envelope[PaymentIntentOut]:
    """Mock payment intent (no real PSP). Idempotent per order. (J-BUY-04)"""
    stub()


@router.post(
    "/{order_id}/payment-confirm",
    response_model=Envelope[PaymentOut],
    summary="Confirm the TEST-MODE payment intent",
)
def confirm_payment(
    order_id: str,
    body: PaymentConfirmRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Envelope[PaymentOut]:
    """Confirm the mock intent. ``payment_declined`` (402) when outcome=failed."""
    stub()


# --- Returns nested under an order --------------------------------------------- #
@router.post(
    "/{order_id}/returns",
    response_model=Envelope[ReturnOut],
    status_code=status.HTTP_201_CREATED,
    summary="Request a return for an order",
)
def request_return(order_id: str, body: ReturnCreate) -> Envelope[ReturnOut]:
    """Request a return. Outside-window direct requests yield ``return_window_closed``;
    the agent-assisted path defers to a human (``hitl_pending``). (J-BUY-06)
    """
    stub()
