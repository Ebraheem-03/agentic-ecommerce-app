"""Seller surfaces: store onboarding, list-product, orders, line fulfilment (J-SEL-01..05).

Routers stay thin; seller-scoped business logic lives here. Everything is scoped to the
caller's OWN store: a seller only sees/touches products + order lines that belong to a
store they own (``stores.owner_id == user.id``). Foreign resources 404 (no-leak), matching
the orders ownership pattern.

The agent-backed NUDGES (``GET /seller/nudges`` + accept) are NOT here — Echo owns those.

Store onboarding is one-store-per-seller (v0): a second onboard for a seller with a store
updates the existing profile rather than creating a second store. New stores land in
``draft`` (an incomplete profile blocks publish — products list under a draft store but the
catalog read filters to ``active`` products anyway). Listing a product creates the Product
+ its variants (+ a zeroed inventory row per variant) under the seller's store.

Fulfilment: a line moves to ``fulfilled`` or ``cancelled`` (partial fulfilment across a
multi-line order is allowed — each line is independent). ``pending`` is not a valid target.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ColumnElement, exists, select
from sqlalchemy.orm import Session, selectinload

from app.api.pagination import decode_cursor, encode_cursor
from app.core.errors import APIError
from app.db.models import (
    Inventory,
    Order,
    OrderItem,
    Product,
    Store,
    Variant,
)
from app.schemas.catalog import ProductDetail
from app.schemas.enums import FulfilStatus, ProductStatus, StoreStatus
from app.schemas.envelope import Envelope, ErrorCode, ListEnvelope, PageMeta
from app.schemas.order import OrderSummary
from app.schemas.seller import ProductCreate, StoreOnboardRequest, StoreOut
from app.services import catalog as catalog_service
from app.services import orders as orders_service

# Valid fulfilment targets — a line is fulfilled or cancelled, never reset to pending.
_FULFIL_TARGETS = frozenset({FulfilStatus.fulfilled, FulfilStatus.cancelled})


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _not_found(thing: str) -> APIError:
    return APIError(
        status_code=404,
        code=ErrorCode.not_found,
        message=f"We couldn't find that {thing}.",
    )


def _conflict(message: str) -> APIError:
    return APIError(status_code=409, code=ErrorCode.conflict, message=message)


def _validation(message: str, details: dict[str, object] | None = None) -> APIError:
    return APIError(
        status_code=422,
        code=ErrorCode.validation_error,
        message=message,
        details=details,
    )


def _store_out(store: Store) -> StoreOut:
    return StoreOut(
        id=store.id,
        name=store.name,
        slug=store.slug,
        location=store.location,
        bio=store.bio,
        status=StoreStatus(store.status),
        payout_pct=store.payout_pct,
        created_at=store.created_at,
    )


def _load_own_store(session: Session, user_id: str) -> Store:
    """The caller's store or 404 (must onboard a store before any other seller op)."""
    store = session.scalars(
        select(Store).where(Store.owner_id == user_id)
    ).first()
    if store is None:
        raise _not_found("store")
    return store


# --------------------------------------------------------------------------- #
# Store onboarding.                                                             #
# --------------------------------------------------------------------------- #
def onboard_store(
    session: Session, user_id: str, body: StoreOnboardRequest
) -> tuple[StoreOut, int]:
    """Create or update the caller's store. Returns ``(out, status_code)``.

    First onboard -> 201 (new draft store). A seller with a store -> update the profile
    (200). The slug is globally unique; a slug taken by ANOTHER store -> 409 conflict.
    """
    existing = session.scalars(
        select(Store).where(Store.owner_id == user_id)
    ).first()

    slug_owner = session.scalars(
        select(Store).where(Store.slug == body.slug)
    ).first()
    if slug_owner is not None and (existing is None or slug_owner.id != existing.id):
        raise _conflict("That store slug is already taken.")

    if existing is None:
        store = Store(
            owner_id=user_id,
            name=body.name,
            slug=body.slug,
            location=body.location,
            bio=body.bio,
            status=StoreStatus.draft.value,
        )
        session.add(store)
        session.flush()
        session.refresh(store)
        return _store_out(store), 201

    existing.name = body.name
    existing.slug = body.slug
    existing.location = body.location
    existing.bio = body.bio
    session.flush()
    session.refresh(existing)
    return _store_out(existing), 200


# --------------------------------------------------------------------------- #
# List a product.                                                              #
# --------------------------------------------------------------------------- #
def create_product(
    session: Session, user_id: str, body: ProductCreate
) -> Envelope[ProductDetail]:
    """List a product under the caller's store (>=1 variant). Labelled validation errors.

    The product slug + each variant SKU are globally unique; a collision -> 409 conflict
    naming the offending field. New products land ``active`` so they surface in the
    catalog read immediately. Each variant gets a zeroed inventory row (qty_on_hand 0).
    """
    store = _load_own_store(session, user_id)

    if session.scalars(select(Product).where(Product.slug == body.slug)).first():
        raise _conflict(f"A product with slug {body.slug!r} already exists.")

    skus = [v.sku for v in body.variants]
    if len(set(skus)) != len(skus):
        raise _validation("Variant SKUs must be unique within a product.")
    clashing = session.scalars(
        select(Variant.sku).where(Variant.sku.in_(skus))
    ).first()
    if clashing is not None:
        raise _conflict(f"A variant with SKU {clashing!r} already exists.")

    product = Product(
        store_id=store.id,
        title=body.title,
        slug=body.slug,
        description=body.description,
        category=body.category,
        attributes=body.attributes,
        status=ProductStatus.active.value,
    )
    for v in body.variants:
        variant = Variant(
            sku=v.sku,
            options=v.options,
            price_minor=v.price_minor,
            currency=v.currency,
            is_active=True,
        )
        variant.inventory = Inventory(qty_on_hand=v.qty_on_hand, qty_reserved=0)
        product.variants.append(variant)
    session.add(product)
    session.flush()

    # Re-load eagerly so the projection never lazy-loads post-flush.
    fresh = session.scalars(
        select(Product)
        .where(Product.id == product.id)
        .options(*catalog_service._eager_product())  # noqa: SLF001 — same package intent
    ).first()
    assert fresh is not None
    return Envelope(data=catalog_service._product_detail(fresh))  # noqa: SLF001


# --------------------------------------------------------------------------- #
# Seller orders + fulfilment.                                                  #
# --------------------------------------------------------------------------- #
def _seller_item_exists_clause(store_id: str) -> ColumnElement[bool]:
    """A correlated EXISTS: the order has >=1 item whose variant->product is this store's."""
    return exists(
        select(OrderItem.id)
        .join(Variant, OrderItem.variant_id == Variant.id)
        .join(Product, Variant.product_id == Product.id)
        .where(OrderItem.order_id == Order.id, Product.store_id == store_id)
    )


def list_orders(
    session: Session,
    user_id: str,
    *,
    cursor: str | None,
    limit: int,
) -> ListEnvelope[OrderSummary]:
    """Orders containing >=1 of the seller's items, newest first, cursor-paginated."""
    store = _load_own_store(session, user_id)

    stmt = (
        select(Order)
        .where(_seller_item_exists_clause(store.id))
        .options(selectinload(Order.items))
        .order_by(Order.placed_at.desc(), Order.id.desc())
    )
    if cursor is not None:
        pos = decode_cursor(cursor)
        stmt = stmt.where(
            (Order.placed_at < pos.created_at)
            | ((Order.placed_at == pos.created_at) & (Order.id < pos.id))
        )

    rows = list(session.scalars(stmt.limit(limit + 1)))
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = (
        encode_cursor(page[-1].placed_at, page[-1].id) if has_more and page else None
    )
    return ListEnvelope(
        data=[orders_service._order_summary(o) for o in page],  # noqa: SLF001
        meta=PageMeta(next_cursor=next_cursor, limit=limit, total=None),
    )


def fulfil_item(
    session: Session,
    user_id: str,
    order_item_id: str,
    fulfil_status: FulfilStatus,
) -> Envelope[OrderSummary]:
    """Mark one of the seller's order lines fulfilled / cancelled (partial allowed).

    Scoped to the seller's store via the item's variant->product->store chain; a line on
    a foreign store -> 404 (no-leak). ``pending`` is not a valid target -> 422.
    """
    if fulfil_status not in _FULFIL_TARGETS:
        raise _validation("A line can only be marked fulfilled or cancelled.")

    store = _load_own_store(session, user_id)
    if not _is_uuid(order_item_id):
        raise _not_found("order item")

    item = session.scalars(
        select(OrderItem)
        .join(Variant, OrderItem.variant_id == Variant.id)
        .join(Product, Variant.product_id == Product.id)
        .where(OrderItem.id == order_item_id, Product.store_id == store.id)
    ).first()
    if item is None:
        # Either no such line, or it belongs to another store — same no-leak 404.
        raise _not_found("order item")

    item.fulfil_status = fulfil_status.value
    session.flush()

    order = session.scalars(
        select(Order)
        .where(Order.id == item.order_id)
        .options(selectinload(Order.items))
    ).first()
    assert order is not None
    return Envelope(data=orders_service._order_summary(order))  # noqa: SLF001
