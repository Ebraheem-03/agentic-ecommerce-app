"""Catalog routes: products (list/detail), reviews, stores (US-E4-06).

Product list + detail and store detail are LIVE (real handlers reading the seeded
catalog through ``app.services.catalog``). Reviews (list/create) remain contract stubs
— they land in a later story. All reads here are public (no auth), per contract-v0.

Mounted at ``/products`` + ``/stores`` (no ``/catalog`` prefix). The success envelope is
``{data, meta}``; lists carry cursor pagination in ``meta``; 404s render the canonical
error envelope. Inventory surfaces per-variant via ``VariantOut.in_stock`` (+ restock eta).
"""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api._contract import ERROR_RESPONSES, stub
from app.api.deps import SessionDep
from app.schemas.catalog import (
    ProductDetail,
    ProductSummary,
    ReviewCreate,
    ReviewOut,
    StoreDetail,
)
from app.schemas.envelope import Envelope, ListEnvelope
from app.services import catalog as catalog_service

router = APIRouter(tags=["catalog"], responses=ERROR_RESPONSES)


@router.get(
    "/products",
    response_model=ListEnvelope[ProductSummary],
    summary="List / browse products",
)
def list_products(
    session: SessionDep,
    category: str | None = Query(default=None),
    store_id: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=24, ge=1, le=100),
) -> ListEnvelope[ProductSummary]:
    """Browse active products, filterable by category/store; cursor-paginated. (J-BUY-01)"""
    return catalog_service.list_products(
        session, category=category, store_id=store_id, cursor=cursor, limit=limit
    )


@router.get(
    "/products/{id_or_slug}",
    response_model=Envelope[ProductDetail],
    summary="Product detail (variants, images, inventory, rating rollup)",
)
def get_product(id_or_slug: str, session: SessionDep) -> Envelope[ProductDetail]:
    """Full product detail by id or slug; 404 if missing/inactive. (J-BUY-02)"""
    return Envelope(data=catalog_service.get_product(session, id_or_slug))


@router.get(
    "/products/{product_id}/reviews",
    response_model=ListEnvelope[ReviewOut],
    summary="List product reviews",
)
def list_reviews(
    product_id: str,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> ListEnvelope[ReviewOut]:
    """Reviews for a product (newest first). (contract stub — later story)"""
    stub()


@router.post(
    "/products/{product_id}/reviews",
    response_model=Envelope[ReviewOut],
    status_code=status.HTTP_201_CREATED,
    summary="Create a review (one per user/product)",
)
def create_review(product_id: str, body: ReviewCreate) -> Envelope[ReviewOut]:
    """Add a review; recomputes the rating rollup. (contract stub — later story)"""
    stub()


@router.get(
    "/stores/{id_or_slug}",
    response_model=Envelope[StoreDetail],
    summary="Store detail (storefront)",
)
def get_store(id_or_slug: str, session: SessionDep) -> Envelope[StoreDetail]:
    """Storefront detail for a single store by id or slug; 404 if missing."""
    return Envelope(data=catalog_service.get_store(session, id_or_slug))
