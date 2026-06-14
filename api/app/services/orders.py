"""Checkout, test-mode payment, and inventory reservation (US-E4-10).

Routers stay thin; the order lifecycle + payment state machine + inventory math live
here. Mirrors ``app.services.cart`` / ``app.services.catalog``. See ADR-0028 for the
ratified decisions this implements.

State machine (single multi-store order, per-item snapshots frozen at checkout):

  POST /orders (checkout)
    open cart (>=1 line) -> Order(status=placed) + OrderItem snapshots
    reserve stock per line: qty_reserved += qty   (available = on_hand - reserved)
    empty cart      -> 409 empty_cart
    any line short  -> 409 out_of_stock  (ATOMIC: nothing reserved, no order created)
    source cart     -> status=converted

  POST /orders/{id}/payment-intent
    -> Payment(status=pending) + mock client_secret/provider_ref, amount = order total.
    If a prior decline already RELEASED the reservation, re-check availability and
    re-reserve here (retry-after-decline edge) so capture has stock to draw down.

  POST /orders/{id}/payment-confirm
    outcome=captured (default) -> Payment.status=captured; CAPTURE inventory:
        qty_on_hand -= qty AND qty_reserved -= qty (floored at 0) per line.
    outcome=failed             -> 402 payment_declined; Payment.status=failed;
        RELEASE reservation: qty_reserved -= qty (floored at 0); order stays placed.

Concurrency: inventory rows are taken ``SELECT ... FOR UPDATE`` so concurrent
checkouts/captures serialize and never oversell. ``qty_on_hand``/``qty_reserved`` are
floored at 0 so the DB CHECK (>= 0) can never trip.

SHIPPING/TAX (v0 rule, ADR-0028): flat $0 shipping + $0 tax — total == subtotal. The
columns exist so a real rule can land later without a schema or contract change.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.interfaces import LoaderOption

from app.db.models import (
    Cart,
    Inventory,
    Order,
    OrderItem,
    Payment,
    Variant,
)
from app.db.models.cart import CartItem
from app.db.models.catalog import Product
from app.schemas.enums import (
    CartStatus,
    FulfilStatus,
    OrderStatus,
    PaymentStatus,
)
from app.schemas.order import (
    OrderDetail,
    OrderItemOut,
    OrderSummary,
    PaymentIntentOut,
    PaymentOut,
)
from app.services import idempotency as idempotency_service
from app.services.errors import (
    empty_cart_error,
    not_found,
    out_of_stock,
    payment_declined,
)

_OPEN = CartStatus.open.value
_CONVERTED = CartStatus.converted.value
_PLACED = OrderStatus.placed.value
_DEFAULT_CURRENCY = "USD"

# v0 shipping/tax rule (ADR-0028): flat zero. Centralized so a real rule is one edit.
_SHIPPING_MINOR = 0
_TAX_MINOR = 0


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


# --------------------------------------------------------------------------- #
# Order number — human-friendly, unique-enough (collision-checked at insert).  #
# --------------------------------------------------------------------------- #
def _generate_order_number() -> str:
    """``HEA-YYYYMMDD-XXXXXX`` (date + 6 url-safe chars). Unique col guards collisions."""
    today = datetime.now(UTC).strftime("%Y%m%d")
    suffix = secrets.token_hex(3).upper()  # 6 hex chars
    return f"HEA-{today}-{suffix}"


# --------------------------------------------------------------------------- #
# Inventory — locked reads so concurrent checkout/capture serialize.           #
# --------------------------------------------------------------------------- #
def _lock_inventory(session: Session, variant_ids: list[str]) -> dict[str, Inventory]:
    """Lock the inventory rows for the given variants (``FOR UPDATE``), keyed by variant.

    Locking up front (in a stable order via the ``IN`` set) keeps concurrent
    checkouts/captures from deadlocking and prevents oversell.
    """
    if not variant_ids:
        return {}
    rows = session.scalars(
        select(Inventory)
        .where(Inventory.variant_id.in_(variant_ids))
        .order_by(Inventory.variant_id)
        .with_for_update()
    ).all()
    return {row.variant_id: row for row in rows}


def _available(inv: Inventory | None) -> int:
    if inv is None:
        return 0
    return inv.qty_on_hand - inv.qty_reserved


# --------------------------------------------------------------------------- #
# Projection helpers.                                                          #
# --------------------------------------------------------------------------- #
def _eager_order() -> list[LoaderOption]:
    return [
        selectinload(Order.items),
        selectinload(Order.payments),
    ]


def _order_item_out(item: OrderItem) -> OrderItemOut:
    return OrderItemOut(
        id=item.id,
        variant_id=item.variant_id,
        title_snapshot=item.title_snapshot,
        options_snapshot=item.options_snapshot,
        store_name_snapshot=item.store_name_snapshot,
        unit_price_minor=item.unit_price_minor,
        qty=item.qty,
        fulfil_status=FulfilStatus(item.fulfil_status),
    )


def _payment_out(payment: Payment) -> PaymentOut:
    return PaymentOut(
        id=payment.id,
        status=PaymentStatus(payment.status),
        provider_ref=payment.provider_ref,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        created_at=payment.created_at,
    )


def _order_detail(order: Order) -> OrderDetail:
    items = sorted(order.items, key=lambda it: it.id)
    payments = sorted(order.payments, key=lambda p: p.created_at)
    return OrderDetail(
        id=order.id,
        order_number=order.order_number,
        status=OrderStatus(order.status),
        total_minor=order.total_minor,
        currency=order.currency,
        item_count=sum(it.qty for it in items),
        placed_at=order.placed_at,
        subtotal_minor=order.subtotal_minor,
        shipping_minor=order.shipping_minor,
        tax_minor=order.tax_minor,
        ship_address=order.ship_address,
        items=[_order_item_out(it) for it in items],
        payments=[_payment_out(p) for p in payments],
        updated_at=order.updated_at,
    )


def _order_summary(order: Order) -> OrderSummary:
    return OrderSummary(
        id=order.id,
        order_number=order.order_number,
        status=OrderStatus(order.status),
        total_minor=order.total_minor,
        currency=order.currency,
        item_count=sum(it.qty for it in order.items),
        placed_at=order.placed_at,
    )


def _load_own_order(session: Session, user_id: str, order_id: str) -> Order:
    """The caller's order (eager items+payments) or 404 — never leaks another's order."""
    if not _is_uuid(order_id):
        raise not_found("order")
    order = session.scalars(
        select(Order)
        .where(Order.id == order_id, Order.user_id == user_id)
        .options(*_eager_order())
    ).first()
    if order is None:
        raise not_found("order")
    return order


# --------------------------------------------------------------------------- #
# Checkout.                                                                    #
# --------------------------------------------------------------------------- #
def _load_open_cart_for_checkout(session: Session, user_id: str) -> Cart:
    """The caller's open cart with items+variant->product->store eager-loaded."""
    cart = session.scalars(
        select(Cart)
        .where(Cart.user_id == user_id, Cart.status == _OPEN)
        .options(
            selectinload(Cart.items)
            .selectinload(CartItem.variant)
            .options(
                selectinload(Variant.product).selectinload(Product.store),
            )
        )
    ).first()
    if cart is None or not cart.items:
        raise empty_cart_error()
    return cart


def checkout(
    session: Session,
    user_id: str,
    *,
    ship_address: dict[str, object],
    idempotency_key: str | None,
) -> tuple[OrderDetail, int]:
    """Convert the open cart into a placed order, reserving stock atomically.

    Returns ``(detail, status_code)`` — 201 on a fresh checkout, or the stored
    201 body on an idempotent replay. ``empty_cart`` (409) when the cart is empty;
    ``out_of_stock`` (409, atomic) when any line exceeds available stock.
    """
    endpoint = "orders:checkout"
    replay = idempotency_service.lookup(session, user_id, idempotency_key, endpoint)
    if replay is not None:
        return OrderDetail.model_validate(replay.body), replay.status_code

    cart = _load_open_cart_for_checkout(session, user_id)

    variant_ids = [it.variant_id for it in cart.items]
    inv_by_variant = _lock_inventory(session, variant_ids)

    # Validate the WHOLE cart before mutating anything (atomic all-or-nothing).
    for item in cart.items:
        inv = inv_by_variant.get(item.variant_id)
        if item.qty > _available(inv):
            raise out_of_stock(_available(inv))

    subtotal = sum(it.variant.price_minor * it.qty for it in cart.items)
    currency = cart.items[0].variant.currency if cart.items else _DEFAULT_CURRENCY

    order = Order(
        order_number=_generate_order_number(),
        user_id=user_id,
        cart_id=cart.id,
        status=_PLACED,
        subtotal_minor=subtotal,
        shipping_minor=_SHIPPING_MINOR,
        tax_minor=_TAX_MINOR,
        total_minor=subtotal + _SHIPPING_MINOR + _TAX_MINOR,
        currency=currency,
        ship_address=ship_address,
    )
    for item in cart.items:
        variant = item.variant
        product = variant.product
        order.items.append(
            OrderItem(
                variant_id=variant.id,
                title_snapshot=product.title,
                options_snapshot=variant.options,
                store_name_snapshot=product.store.name,
                unit_price_minor=variant.price_minor,
                qty=item.qty,
                fulfil_status=FulfilStatus.pending.value,
            )
        )
        # Reserve: available shrinks, on-hand untouched until capture.
        inv_by_variant[variant.id].qty_reserved += item.qty

    cart.status = _CONVERTED
    session.add(order)
    session.flush()

    # Re-load eager so the projection never triggers a lazy load post-flush.
    fresh = _load_own_order(session, user_id, order.id)
    detail = _order_detail(fresh)

    idempotency_service.store(
        session,
        user_id,
        idempotency_key,
        endpoint,
        status_code=201,
        body=detail,
    )
    return detail, 201


# --------------------------------------------------------------------------- #
# Reads.                                                                       #
# --------------------------------------------------------------------------- #
def list_orders(session: Session, user_id: str) -> list[OrderSummary]:
    """The caller's orders, newest first (placed_at DESC, id DESC tiebreaker)."""
    orders = session.scalars(
        select(Order)
        .where(Order.user_id == user_id)
        .options(selectinload(Order.items))
        .order_by(Order.placed_at.desc(), Order.id.desc())
    ).all()
    return [_order_summary(o) for o in orders]


def get_order(session: Session, user_id: str, order_id: str) -> OrderDetail:
    """The caller's order detail + payments; 404 for a missing/foreign order."""
    return _order_detail(_load_own_order(session, user_id, order_id))


# --------------------------------------------------------------------------- #
# Test-mode payment.                                                           #
# --------------------------------------------------------------------------- #
def create_payment_intent(
    session: Session,
    user_id: str,
    order_id: str,
    *,
    idempotency_key: str | None,
) -> tuple[PaymentIntentOut, int]:
    """Create a mock payment intent for the caller's order (amount = order total).

    Idempotent per (user, key). If a prior decline RELEASED the reservation, re-check
    availability and re-reserve here so a later capture has stock to draw down.
    """
    endpoint = f"orders:payment-intent:{order_id}"
    replay = idempotency_service.lookup(session, user_id, idempotency_key, endpoint)
    if replay is not None:
        return PaymentIntentOut.model_validate(replay.body), replay.status_code

    order = _load_own_order(session, user_id, order_id)

    # Re-reserve if a prior failed confirm released this order's reservation. We detect
    # "released" by the absence of a pending/captured payment AND lock+re-check stock.
    _ensure_reserved(session, order)

    payment = Payment(
        order_id=order.id,
        status=PaymentStatus.pending.value,
        provider_ref=f"pi_test_{secrets.token_hex(8)}",
        amount_minor=order.total_minor,
        currency=order.currency,
    )
    session.add(payment)
    session.flush()

    out = PaymentIntentOut(
        payment_id=payment.id,
        client_secret=f"seti_test_{secrets.token_urlsafe(16)}",
        status=PaymentStatus(payment.status),
        amount_minor=payment.amount_minor,
        currency=payment.currency,
    )
    idempotency_service.store(
        session,
        user_id,
        idempotency_key,
        endpoint,
        status_code=201,
        body=out,
    )
    return out, 201


def _ensure_reserved(session: Session, order: Order) -> None:
    """Re-reserve this order's lines if a prior decline released them.

    Reservation is HELD continuously from checkout until the payment is either captured
    (reserved->sold) or declined (released). So the order's stock is already reserved
    when there are NO payments yet (fresh checkout) or a live pending/captured one. We
    only re-reserve when the most recent payment was a decline that released the lines —
    the retry-after-decline edge — taking a row lock and re-checking availability so we
    never oversell.
    """
    if not order.payments:
        return  # fresh checkout reservation still holds — do not double-reserve

    latest = max(order.payments, key=lambda p: p.created_at)
    if latest.status != PaymentStatus.failed.value:
        return  # a live pending/captured payment means stock is still reserved/sold

    variant_ids = [it.variant_id for it in order.items if it.variant_id is not None]
    inv_by_variant = _lock_inventory(session, variant_ids)
    for item in order.items:
        if item.variant_id is None:
            continue
        inv = inv_by_variant.get(item.variant_id)
        if item.qty > _available(inv):
            raise out_of_stock(_available(inv))
    for item in order.items:
        if item.variant_id is None:
            continue
        inv_by_variant[item.variant_id].qty_reserved += item.qty


def confirm_payment(
    session: Session,
    user_id: str,
    order_id: str,
    *,
    payment_id: str,
    outcome: PaymentStatus,
    idempotency_key: str | None,
) -> tuple[PaymentOut, int]:
    """Confirm the mock intent deterministically by ``outcome``.

    ``captured`` -> 200 + capture inventory (on_hand-=qty, reserved-=qty).
    ``failed``   -> 402 payment_declined + release reservation (reserved-=qty);
    the payment row lands ``failed`` and the order stays ``placed`` (unpaid).
    """
    endpoint = f"orders:payment-confirm:{order_id}"
    replay = idempotency_service.lookup(session, user_id, idempotency_key, endpoint)
    if replay is not None:
        if replay.status_code == 402:
            raise payment_declined()
        return PaymentOut.model_validate(replay.body), replay.status_code

    order = _load_own_order(session, user_id, order_id)
    payment = next((p for p in order.payments if p.id == payment_id), None)
    if payment is None:
        raise not_found("payment")

    variant_ids = [it.variant_id for it in order.items if it.variant_id is not None]
    inv_by_variant = _lock_inventory(session, variant_ids)

    if outcome == PaymentStatus.failed:
        # Decline: release the reservation; order stays placed (unpaid).
        for item in order.items:
            if item.variant_id is None:
                continue
            inv = inv_by_variant.get(item.variant_id)
            if inv is not None:
                inv.qty_reserved = max(0, inv.qty_reserved - item.qty)
        payment.status = PaymentStatus.failed.value
        session.flush()
        idempotency_service.store(
            session,
            user_id,
            idempotency_key,
            endpoint,
            status_code=402,
            body={"code": "payment_declined"},
        )
        # The decline is a BUSINESS outcome, not a fault: the reservation-release +
        # payment=failed + idempotency row MUST persist even though we signal 402 by
        # raising. The request-scoped session rolls back on any exception (deps.py), so
        # commit here first, then raise the (already-persisted) declined signal.
        session.commit()
        raise payment_declined()

    # Capture: move reserved -> sold. Floor both at 0 (defends the CHECK >= 0).
    for item in order.items:
        if item.variant_id is None:
            continue
        inv = inv_by_variant.get(item.variant_id)
        if inv is not None:
            inv.qty_on_hand = max(0, inv.qty_on_hand - item.qty)
            inv.qty_reserved = max(0, inv.qty_reserved - item.qty)
    payment.status = PaymentStatus.captured.value
    session.flush()

    out = _payment_out(payment)
    idempotency_service.store(
        session,
        user_id,
        idempotency_key,
        endpoint,
        status_code=200,
        body=out,
    )
    return out, 200
