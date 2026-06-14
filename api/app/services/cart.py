"""Cart write/read logic — the single open cart per user + its items (US-E4-09).

Routers stay thin; everything that touches the ORM, the cart invariants, and the
inventory math lives here. Mirrors the structure of ``app.services.catalog``.

Invariants honored (already enforced at the schema level, ``app.db.models.cart``):
  * one OPEN cart per user (partial unique ``uq_carts_one_open_per_user``) — GET
    lazily creates it; a concurrent creator that loses the race surfaces
    ``cart_already_open`` (409).
  * ``cart_items.qty > 0`` CHECK — qty is validated >0 by Pydantic; DELETE removes.
  * unique (cart_id, variant_id) — add is an UPSERT: existing line increments qty.

Inventory / out_of_stock: available = ``qty_on_hand - qty_reserved`` (mirrors
``catalog.available_qty``). Add/update raise ``out_of_stock`` (409) when the resulting
line qty exceeds available. This service NEVER mutates inventory — reservation happens
at checkout (US-E4-10), not in the cart.

A line item referenced by id on PATCH/DELETE must belong to the caller's own open cart;
otherwise ``not_found`` (404) — we never leak the existence of another user's line.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.interfaces import LoaderOption

from app.core.errors import APIError
from app.db.models import Variant
from app.db.models.cart import Cart, CartItem
from app.schemas.cart import CartItemOut, CartOut
from app.schemas.enums import CartStatus
from app.schemas.envelope import ErrorCode

_OPEN = CartStatus.open.value


def _not_found(thing: str) -> APIError:
    return APIError(
        status_code=404,
        code=ErrorCode.not_found,
        message=f"We couldn't find that {thing}.",
    )


def _out_of_stock(available: int) -> APIError:
    return APIError(
        status_code=409,
        code=ErrorCode.out_of_stock,
        message="That's more than we have in stock right now.",
        details={"available": available},
    )


def _cart_already_open() -> APIError:
    return APIError(
        status_code=409,
        code=ErrorCode.cart_already_open,
        message="You already have an open cart.",
    )


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _variant_available(variant: Variant) -> int:
    """Sellable quantity = on-hand minus reserved (0 when no inventory row)."""
    inv = variant.inventory
    if inv is None:
        return 0
    return inv.qty_on_hand - inv.qty_reserved


def _eager_cart() -> list[LoaderOption]:
    """Eager-load items + each item's variant->product/inventory (no N+1 on project)."""
    return [
        selectinload(Cart.items)
        .selectinload(CartItem.variant)
        .options(
            selectinload(Variant.product),
            selectinload(Variant.inventory),
        ),
    ]


def _load_open_cart(session: Session, user_id: str) -> Cart | None:
    """The caller's single open cart, fully eager-loaded for projection (or None)."""
    stmt = (
        select(Cart)
        .where(Cart.user_id == user_id, Cart.status == _OPEN)
        .options(*_eager_cart())
    )
    return session.scalars(stmt).first()


def _create_open_cart(session: Session, user_id: str) -> Cart:
    """Insert a fresh open cart for the user, surfacing the one-open race as 409."""
    cart = Cart(user_id=user_id, status=_OPEN)
    session.add(cart)
    try:
        session.flush()
    except IntegrityError as exc:
        # Lost the one-open-cart-per-user race (partial unique).
        session.rollback()
        raise _cart_already_open() from exc
    return cart


def _get_or_create_open_cart(session: Session, user_id: str) -> Cart:
    cart = _load_open_cart(session, user_id)
    if cart is not None:
        return cart
    _create_open_cart(session, user_id)
    # Re-load with eager options so projection is N+1-free even right after create.
    reloaded = _load_open_cart(session, user_id)
    assert reloaded is not None  # we just created it in this transaction
    return reloaded


def _item_out(item: CartItem) -> CartItemOut:
    variant = item.variant
    product = variant.product
    return CartItemOut(
        id=item.id,
        variant_id=variant.id,
        product_id=product.id,
        title=product.title,
        sku=variant.sku,
        options=variant.options,
        unit_price_minor=variant.price_minor,
        currency=variant.currency,
        qty=item.qty,
        line_total_minor=variant.price_minor * item.qty,
        in_stock=_variant_available(variant) > 0,
        added_at=item.added_at,
    )


def _cart_out(cart: Cart) -> CartOut:
    items = sorted(cart.items, key=lambda it: (it.added_at, it.id))
    item_outs = [_item_out(it) for it in items]
    return CartOut(
        id=cart.id,
        status=CartStatus(cart.status),
        items=item_outs,
        subtotal_minor=sum(it.line_total_minor for it in item_outs),
        currency=item_outs[0].currency if item_outs else "USD",
        item_count=sum(it.qty for it in item_outs),
        updated_at=cart.updated_at,
    )


def get_cart(session: Session, user_id: str) -> CartOut:
    """Return (lazily creating if needed) the caller's single open cart."""
    return _cart_out(_get_or_create_open_cart(session, user_id))


def _load_variant(session: Session, variant_id: str) -> Variant:
    if not _is_uuid(variant_id):
        raise _not_found("variant")
    variant = session.get(
        Variant,
        variant_id,
        options=[selectinload(Variant.inventory)],
    )
    if variant is None or not variant.is_active:
        raise _not_found("variant")
    return variant


def add_item(session: Session, user_id: str, *, variant_id: str, qty: int) -> CartOut:
    """Add/increment a variant in the open cart (idempotent upsert on (cart, variant))."""
    variant = _load_variant(session, variant_id)
    cart = _get_or_create_open_cart(session, user_id)

    existing = next((it for it in cart.items if it.variant_id == variant.id), None)
    new_qty = (existing.qty + qty) if existing is not None else qty

    available = _variant_available(variant)
    if new_qty > available:
        raise _out_of_stock(available)

    if existing is not None:
        existing.qty = new_qty
        session.flush()
        return _cart_out(cart)

    cart.items.append(CartItem(variant_id=variant.id, qty=qty))
    session.flush()
    # Re-load so the freshly-inserted line's (lazy="raise") variant nav is eager —
    # the projection never triggers a lazy load.
    reloaded = _load_open_cart(session, user_id)
    assert reloaded is not None
    return _cart_out(reloaded)


def _load_own_item(session: Session, user_id: str, item_id: str) -> tuple[Cart, CartItem]:
    """The caller's open cart + the named line; 404 if the line isn't theirs."""
    cart = _load_open_cart(session, user_id)
    if cart is None:
        raise _not_found("cart item")
    if not _is_uuid(item_id):
        raise _not_found("cart item")
    item = next((it for it in cart.items if it.id == item_id), None)
    if item is None:
        raise _not_found("cart item")
    return cart, item


def update_item(session: Session, user_id: str, item_id: str, *, qty: int) -> CartOut:
    """Set absolute line quantity (qty>0); ``out_of_stock`` if it exceeds available."""
    cart, item = _load_own_item(session, user_id, item_id)

    available = _variant_available(item.variant)
    if qty > available:
        raise _out_of_stock(available)

    item.qty = qty
    session.flush()
    return _cart_out(cart)


def remove_item(session: Session, user_id: str, item_id: str) -> CartOut:
    """Remove a line from the caller's open cart."""
    cart, item = _load_own_item(session, user_id, item_id)
    cart.items.remove(item)
    session.flush()
    return _cart_out(cart)
