"""Cart routes (US-E4-09). One open cart per user; thin handlers over ``services.cart``.

All four endpoints require an authenticated user (``require_user``) and resolve the DB
session via ``get_session``. The success envelope is ``{data, meta}`` (``CartOut``);
errors render the canonical envelope. Business logic, the cart invariants, and the
inventory math live in ``app.services.cart`` — handlers just wire deps -> service.

Layer split: these are handler-level (status + envelope + DB side effects). Juno owns
the full checkout E2E (US-QA-D11). Order/payment + reservation are US-E4-10 (separate
file) — the cart never mutates inventory here.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api._contract import ERROR_RESPONSES
from app.api.deps import CurrentUser, SessionDep
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartOut
from app.schemas.envelope import Envelope
from app.services import cart as cart_service

router = APIRouter(prefix="/cart", tags=["cart"], responses=ERROR_RESPONSES)


@router.get("", response_model=Envelope[CartOut], summary="Get the current open cart")
def get_cart(user: CurrentUser, session: SessionDep) -> Envelope[CartOut]:
    """Return (or lazily create) the caller's single open cart. (J-BUY-03)"""
    return Envelope(data=cart_service.get_cart(session, user.id))


@router.post(
    "/items",
    response_model=Envelope[CartOut],
    status_code=status.HTTP_201_CREATED,
    summary="Add an item (upsert qty) to the cart",
)
def add_item(
    body: CartItemAdd, user: CurrentUser, session: SessionDep
) -> Envelope[CartOut]:
    """Add/increment a variant (idempotent upsert). ``out_of_stock`` if short. (J-BUY-03)"""
    return Envelope(
        data=cart_service.add_item(
            session, user.id, variant_id=body.variant_id, qty=body.qty
        )
    )


@router.patch(
    "/items/{item_id}",
    response_model=Envelope[CartOut],
    summary="Update a line item quantity (qty>0)",
)
def update_item(
    item_id: str, body: CartItemUpdate, user: CurrentUser, session: SessionDep
) -> Envelope[CartOut]:
    """Set absolute quantity for a line (must be > 0; use DELETE to remove)."""
    return Envelope(
        data=cart_service.update_item(session, user.id, item_id, qty=body.qty)
    )


@router.delete(
    "/items/{item_id}",
    response_model=Envelope[CartOut],
    summary="Remove a line item",
)
def remove_item(
    item_id: str, user: CurrentUser, session: SessionDep
) -> Envelope[CartOut]:
    """Remove a line from the cart."""
    return Envelope(data=cart_service.remove_item(session, user.id, item_id))
