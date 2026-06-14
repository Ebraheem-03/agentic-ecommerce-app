"""Catalog read logic — project ORM rows onto contract-v0 catalog DTOs (US-E4-06).

This is the read side of the catalog group: product list (cursor-paginated), product
detail (variants + images + inventory + rating rollup), and store detail. Routers stay
thin; everything that touches the ORM and the inventory math lives here.

Inventory / stock signal (contract ``VariantOut.in_stock``):
    available = qty_on_hand - qty_reserved
    in_stock  = available > 0
A variant with no ``inventory`` row, or with available <= 0, surfaces ``in_stock=False``
(the seeded ``wallet_oos`` SKU, qty_on_hand=0). ``restock_eta_days`` is passed through so
the UI can show "back in N days" for low-stock / out-of-stock variants. The boolean keeps
exact stock counts private while still driving the out-of-stock UI state, per the schema.

Visibility: only ``status='active'`` products are listed/detailed for public reads, and
soft-deleted products (``deleted_at IS NOT NULL``) are never visible. ``from_price_minor``
is the cheapest **active** variant price (null when a product has no active variant).
"""

from __future__ import annotations

import uuid

from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Mapped, Session, selectinload
from sqlalchemy.orm.interfaces import LoaderOption as _AbstractLoad

from app.api.pagination import decode_cursor, encode_cursor
from app.core.errors import APIError
from app.db.models import Product, Store, Variant
from app.db.models.catalog import ProductImage
from app.schemas.catalog import (
    ProductDetail,
    ProductImageOut,
    ProductSummary,
    StoreDetail,
    StoreSummary,
    VariantOut,
)
from app.schemas.enums import ProductStatus, StoreStatus
from app.schemas.envelope import ErrorCode, ListEnvelope, PageMeta

# Highest selectable page size guard mirrors the contract (limit 1-100).
_ACTIVE = ProductStatus.active.value


def _id_or_slug_clause(
    value: str, id_col: Mapped[str], slug_col: Mapped[str]
) -> ColumnElement[bool]:
    """Match a row by slug, plus by id only when ``value`` is a real UUID.

    The id columns are typed ``UUID``; comparing them to an arbitrary slug string would
    make Postgres try to cast the slug to a UUID and raise. So we only OR-in the id
    comparison when the path segment actually parses as a UUID.
    """
    try:
        uuid.UUID(value)
    except ValueError:
        return slug_col == value
    return (id_col == value) | (slug_col == value)


def _not_found(thing: str) -> APIError:
    return APIError(
        status_code=404,
        code=ErrorCode.not_found,
        message=f"We couldn't find that {thing}.",
    )


def _variant_available(variant: Variant) -> int:
    """Sellable quantity = on-hand minus reserved (0 when no inventory row)."""
    inv = variant.inventory
    if inv is None:
        return 0
    return inv.qty_on_hand - inv.qty_reserved


def _variant_out(variant: Variant) -> VariantOut:
    inv = variant.inventory
    return VariantOut(
        id=variant.id,
        sku=variant.sku,
        options=variant.options,
        price_minor=variant.price_minor,
        currency=variant.currency,
        is_active=variant.is_active,
        in_stock=_variant_available(variant) > 0,
        restock_eta_days=inv.restock_eta_days if inv is not None else None,
    )


def _image_out(image: ProductImage) -> ProductImageOut:
    return ProductImageOut(
        id=image.id,
        url=image.url,
        alt=image.alt,
        position=image.position,
        variant_id=image.variant_id,
    )


def _store_summary(store: Store) -> StoreSummary:
    return StoreSummary(
        id=store.id,
        name=store.name,
        slug=store.slug,
        location=store.location,
        status=StoreStatus(store.status),
    )


def _primary_image(images: list[ProductImage]) -> ProductImageOut | None:
    """The product-level cover image: lowest ``position`` (ties broken by id)."""
    if not images:
        return None
    cover = min(images, key=lambda im: (im.position, im.id))
    return _image_out(cover)


def _from_price_minor(variants: list[Variant]) -> int | None:
    """Cheapest active variant price for list/card display (None if none active)."""
    active_prices = [v.price_minor for v in variants if v.is_active]
    return min(active_prices) if active_prices else None


def _product_summary(product: Product) -> ProductSummary:
    return ProductSummary(
        id=product.id,
        title=product.title,
        slug=product.slug,
        category=product.category,
        status=ProductStatus(product.status),
        store=_store_summary(product.store),
        from_price_minor=_from_price_minor(list(product.variants)),
        currency=_summary_currency(product),
        primary_image=_primary_image(list(product.images)),
        rating_avg=float(product.rating_avg) if product.rating_avg is not None else None,
        rating_count=product.rating_count,
    )


def _summary_currency(product: Product) -> str:
    """Currency for the card price — the cheapest active variant's, else USD."""
    active = [v for v in product.variants if v.is_active]
    if not active:
        return "USD"
    cheapest = min(active, key=lambda v: v.price_minor)
    return cheapest.currency


def _product_detail(product: Product) -> ProductDetail:
    return ProductDetail(
        id=product.id,
        title=product.title,
        slug=product.slug,
        category=product.category,
        status=ProductStatus(product.status),
        store=_store_summary(product.store),
        from_price_minor=_from_price_minor(list(product.variants)),
        currency=_summary_currency(product),
        primary_image=_primary_image(list(product.images)),
        rating_avg=float(product.rating_avg) if product.rating_avg is not None else None,
        rating_count=product.rating_count,
        description=product.description,
        attributes=product.attributes,
        variants=[_variant_out(v) for v in product.variants],
        images=[_image_out(im) for im in product.images],
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def _eager_product() -> list[_AbstractLoad]:
    """Eager-load options so projection never lazy-loads (and N+1s) per product."""
    return [
        selectinload(Product.store),
        selectinload(Product.images),
        selectinload(Product.variants).selectinload(Variant.inventory),
    ]


def list_products(
    session: Session,
    *,
    category: str | None,
    store_id: str | None,
    cursor: str | None,
    limit: int,
) -> ListEnvelope[ProductSummary]:
    """Browse active products, newest-first, cursor-paginated (contract-v0)."""
    stmt = (
        select(Product)
        .where(Product.status == _ACTIVE, Product.deleted_at.is_(None))
        .options(*_eager_product())
        .order_by(Product.created_at.desc(), Product.id.desc())
    )
    if category is not None:
        stmt = stmt.where(Product.category == category)
    if store_id is not None:
        stmt = stmt.where(Product.store_id == store_id)
    if cursor is not None:
        pos = decode_cursor(cursor)
        # Keyset: rows strictly "after" the cursor in (created_at DESC, id DESC) order.
        stmt = stmt.where(
            (Product.created_at < pos.created_at)
            | ((Product.created_at == pos.created_at) & (Product.id < pos.id))
        )

    rows = list(session.scalars(stmt.limit(limit + 1)))
    has_more = len(rows) > limit
    page = rows[:limit]

    next_cursor = (
        encode_cursor(page[-1].created_at, page[-1].id) if has_more and page else None
    )
    return ListEnvelope(
        data=[_product_summary(p) for p in page],
        meta=PageMeta(next_cursor=next_cursor, limit=limit, total=None),
    )


def get_product(session: Session, id_or_slug: str) -> ProductDetail:
    """Full product detail by id or slug (404 if missing / not active / deleted)."""
    stmt = (
        select(Product)
        .where(Product.status == _ACTIVE, Product.deleted_at.is_(None))
        .options(*_eager_product())
        .where(_id_or_slug_clause(id_or_slug, Product.id, Product.slug))
    )
    product = session.scalars(stmt).first()
    if product is None:
        raise _not_found("product")
    return _product_detail(product)


def get_store(session: Session, id_or_slug: str) -> StoreDetail:
    """Storefront detail by id or slug (404 if missing)."""
    stmt = select(Store).where(_id_or_slug_clause(id_or_slug, Store.id, Store.slug))
    store = session.scalars(stmt).first()
    if store is None:
        raise _not_found("store")
    return StoreDetail(
        id=store.id,
        name=store.name,
        slug=store.slug,
        location=store.location,
        status=StoreStatus(store.status),
        bio=store.bio,
        created_at=store.created_at,
    )
