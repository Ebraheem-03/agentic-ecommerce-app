"""Cart routes (contract draft). One open cart per user."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api._contract import ERROR_RESPONSES, stub
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartOut
from app.schemas.envelope import Envelope

router = APIRouter(prefix="/cart", tags=["cart"], responses=ERROR_RESPONSES)


@router.get("", response_model=Envelope[CartOut], summary="Get the current open cart")
def get_cart() -> Envelope[CartOut]:
    """Return (or lazily create) the caller's single open cart."""
    stub()


@router.post(
    "/items",
    response_model=Envelope[CartOut],
    status_code=status.HTTP_201_CREATED,
    summary="Add an item (upsert qty) to the cart",
)
def add_item(body: CartItemAdd) -> Envelope[CartOut]:
    """Add/increment a variant. ``out_of_stock`` if insufficient inventory. (J-BUY-03)"""
    stub()


@router.patch(
    "/items/{item_id}",
    response_model=Envelope[CartOut],
    summary="Update a line item quantity (qty>0)",
)
def update_item(item_id: str, body: CartItemUpdate) -> Envelope[CartOut]:
    """Set absolute quantity for a line (must be > 0; use DELETE to remove)."""
    stub()


@router.delete(
    "/items/{item_id}",
    response_model=Envelope[CartOut],
    summary="Remove a line item",
)
def remove_item(item_id: str) -> Envelope[CartOut]:
    """Remove a line from the cart."""
    stub()
