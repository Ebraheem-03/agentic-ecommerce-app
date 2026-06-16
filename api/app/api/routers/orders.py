"""Order + test-mode payment routes (US-E4-10). Thin handlers over ``services.orders``.

All endpoints require an authenticated user (``require_user``) and resolve the DB session
via ``get_session``. The success envelope is ``{data, meta}``; errors render the canonical
envelope (``APIError`` -> closed ``ErrorCode``, never a bare ``HTTPException``).

The order/payment/reservation state machine + inventory math live in
``app.services.orders`` (see its module docstring + ADR-0028). Checkout, payment-intent,
and payment-confirm are idempotent on the ``Idempotency-Key`` header (or the body
fallback) via ``app.services.idempotency`` — replays return the original result.

Returns (``POST /orders/{id}/returns``) stays a contract stub — it lands in a later
returns epic, NOT this story.

LAYER SPLIT: these are handler-level. Juno owns the full checkout E2E (US-QA-D11).
"""

from __future__ import annotations

from fastapi import APIRouter, Header, status

from app.api._contract import ERROR_RESPONSES
from app.api.deps import CurrentUser, SessionDep
from app.schemas.envelope import Envelope, ListEnvelope, PageMeta
from app.schemas.order import (
    CheckoutRequest,
    OrderDetail,
    OrderSummary,
    PaymentConfirmRequest,
    PaymentIntentOut,
    PaymentOut,
)
from app.schemas.returns import ReturnCreate, ReturnOut
from app.services import orders as orders_service
from app.services import returns as returns_service

router = APIRouter(prefix="/orders", tags=["orders"], responses=ERROR_RESPONSES)


@router.post(
    "",
    response_model=Envelope[OrderDetail],
    status_code=status.HTTP_201_CREATED,
    summary="Checkout: create an order from the open cart (idempotent)",
)
def create_order(
    body: CheckoutRequest,
    user: CurrentUser,
    session: SessionDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Envelope[OrderDetail]:
    """Convert the open cart into an order. Replays of the key return the same order.

    ``empty_cart`` (409) if the cart has no items; ``out_of_stock`` (409, atomic) on an
    inventory shortfall. Inventory is reserved per line at checkout. (J-BUY-04)
    """
    detail, _status = orders_service.checkout(
        session,
        user.id,
        ship_address=body.ship_address.model_dump(mode="json"),
        idempotency_key=idempotency_key or body.idempotency_key,
    )
    return Envelope(data=detail)


@router.get("", response_model=ListEnvelope[OrderSummary], summary="List my orders")
def list_orders(user: CurrentUser, session: SessionDep) -> ListEnvelope[OrderSummary]:
    """List the caller's orders, newest first. (J-BUY-05)"""
    summaries = orders_service.list_orders(session, user.id)
    return ListEnvelope(
        data=summaries,
        meta=PageMeta(next_cursor=None, limit=max(len(summaries), 1), total=len(summaries)),
    )


@router.get(
    "/{order_id}",
    response_model=Envelope[OrderDetail],
    summary="Get an order (detail + status)",
)
def get_order(
    order_id: str, user: CurrentUser, session: SessionDep
) -> Envelope[OrderDetail]:
    """Order detail incl. items + payments; a foreign/missing order is 404. (J-BUY-05)"""
    return Envelope(data=orders_service.get_order(session, user.id, order_id))


@router.post(
    "/{order_id}/payment-intent",
    response_model=Envelope[PaymentIntentOut],
    status_code=status.HTTP_201_CREATED,
    summary="Create a TEST-MODE payment intent",
)
def create_payment_intent(
    order_id: str,
    user: CurrentUser,
    session: SessionDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Envelope[PaymentIntentOut]:
    """Mock payment intent (no real PSP), amount = order total. Idempotent. (J-BUY-04)"""
    intent, _status = orders_service.create_payment_intent(
        session, user.id, order_id, idempotency_key=idempotency_key
    )
    return Envelope(data=intent)


@router.post(
    "/{order_id}/payment-confirm",
    response_model=Envelope[PaymentOut],
    summary="Confirm the TEST-MODE payment intent",
)
def confirm_payment(
    order_id: str,
    body: PaymentConfirmRequest,
    user: CurrentUser,
    session: SessionDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Envelope[PaymentOut]:
    """Confirm the mock intent. ``outcome=failed`` -> 402 ``payment_declined`` (order
    stays placed, reservation released); ``captured`` -> 200 + inventory captured.
    """
    payment, _status = orders_service.confirm_payment(
        session,
        user.id,
        order_id,
        payment_id=body.payment_id,
        outcome=body.outcome,
        idempotency_key=idempotency_key,
    )
    return Envelope(data=payment)


# --- Returns nested under an order --------------------------------------------- #
@router.post(
    "/{order_id}/returns",
    response_model=Envelope[ReturnOut],
    status_code=status.HTTP_201_CREATED,
    summary="Request a return for an order",
)
def request_return(
    order_id: str, body: ReturnCreate, user: CurrentUser, session: SessionDep
) -> Envelope[ReturnOut]:
    """Request a return. Outside-window DIRECT requests yield ``return_window_closed``;
    the agent-assisted path (``allow_hitl``) defers to a human (``hitl_pending``). The
    HTTP path is strict (direct): out-of-window -> 409. (J-BUY-06)
    """
    out, _status = returns_service.request_return(
        session, user.id, order_id, body, allow_hitl=False
    )
    return Envelope(data=out)
