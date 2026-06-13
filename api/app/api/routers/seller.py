"""Seller routes (contract draft): store, list-product, nudges, fulfilment."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api._contract import ERROR_RESPONSES, stub
from app.schemas.catalog import ProductDetail
from app.schemas.envelope import Envelope, ListEnvelope
from app.schemas.order import OrderSummary
from app.schemas.seller import (
    FulfilRequest,
    NudgeAcceptRequest,
    NudgeOut,
    ProductCreate,
    StoreOnboardRequest,
    StoreOut,
)

router = APIRouter(prefix="/seller", tags=["seller"], responses=ERROR_RESPONSES)


@router.post(
    "/store",
    response_model=Envelope[StoreOut],
    status_code=status.HTTP_201_CREATED,
    summary="Create / complete the seller store profile",
)
def onboard_store(body: StoreOnboardRequest) -> Envelope[StoreOut]:
    """Onboard a seller store. Incomplete profile blocks publish. (J-SEL-01)"""
    stub()


@router.post(
    "/products",
    response_model=Envelope[ProductDetail],
    status_code=status.HTTP_201_CREATED,
    summary="List a product (create SKU/variants)",
)
def create_product(body: ProductCreate) -> Envelope[ProductDetail]:
    """List a product with >=1 variant. Validation errors are labelled. (J-SEL-02)"""
    stub()


@router.get(
    "/orders",
    response_model=ListEnvelope[OrderSummary],
    summary="Orders containing this seller's items",
)
def seller_orders(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> ListEnvelope[OrderSummary]:
    """Orders the seller must fulfil. (J-SEL-05)"""
    stub()


@router.patch(
    "/order-items/{order_item_id}/fulfil",
    response_model=Envelope[OrderSummary],
    summary="Fulfil / cancel an order line",
)
def fulfil_item(order_item_id: str, body: FulfilRequest) -> Envelope[OrderSummary]:
    """Mark a line fulfilled or cancelled (partial fulfilment allowed). (J-SEL-05)"""
    stub()


@router.get(
    "/nudges",
    response_model=ListEnvelope[NudgeOut],
    summary="Merchandising/pricing nudges (agent-generated)",
)
def list_nudges(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
) -> ListEnvelope[NudgeOut]:
    """Grounded nudges for the seller's catalog. (J-SEL-03)"""
    stub()


@router.post(
    "/nudges/{nudge_id}/accept",
    response_model=Envelope[NudgeOut],
    summary="Accept a nudge (audited, reversible)",
)
def accept_nudge(nudge_id: str, body: NudgeAcceptRequest) -> Envelope[NudgeOut]:
    """Apply a nudge; logs an audited agent_action. (J-SEL-04)"""
    stub()
