"""Catalog routes (contract draft): products, stores, reviews."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api._contract import ERROR_RESPONSES, stub
from app.schemas.catalog import (
    ProductDetail,
    ProductSummary,
    ReviewCreate,
    ReviewOut,
    StoreDetail,
)
from app.schemas.envelope import Envelope, ListEnvelope

router = APIRouter(tags=["catalog"], responses=ERROR_RESPONSES)


@router.get(
    "/products",
    response_model=ListEnvelope[ProductSummary],
    summary="List / browse products",
)
def list_products(
    category: str | None = Query(default=None),
    store_id: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=24, ge=1, le=100),
) -> ListEnvelope[ProductSummary]:
    """Browse active products, filterable by category/store. (J-BUY-01)"""
    stub()


@router.get(
    "/products/{product_id}",
    response_model=Envelope[ProductDetail],
    summary="Product detail (variants, images, rating rollup)",
)
def get_product(product_id: str) -> Envelope[ProductDetail]:
    """Full product detail page payload. (J-BUY-02)"""
    stub()


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
    """Reviews for a product (newest first)."""
    stub()


@router.post(
    "/products/{product_id}/reviews",
    response_model=Envelope[ReviewOut],
    status_code=status.HTTP_201_CREATED,
    summary="Create a review (one per user/product)",
)
def create_review(product_id: str, body: ReviewCreate) -> Envelope[ReviewOut]:
    """Add a review; recomputes the product rating rollup. ``duplicate_review`` on repeat."""
    stub()


@router.get(
    "/stores/{store_id}",
    response_model=Envelope[StoreDetail],
    summary="Store detail (storefront)",
)
def get_store(store_id: str) -> Envelope[StoreDetail]:
    """Storefront detail for a single store."""
    stub()
