"""Return read + decision routes (contract draft).

Request-a-return lives under ``/orders/{id}/returns`` (orders router). These are the
list/get + the support/admin (or HITL) decision endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api._contract import ERROR_RESPONSES, stub
from app.schemas.envelope import Envelope, ListEnvelope
from app.schemas.returns import ReturnDecision, ReturnOut

router = APIRouter(prefix="/returns", tags=["returns"], responses=ERROR_RESPONSES)


@router.get("", response_model=ListEnvelope[ReturnOut], summary="List returns")
def list_returns(
    status_filter: str | None = Query(default=None, alias="status"),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> ListEnvelope[ReturnOut]:
    """Buyer sees own returns; support/admin can filter all (incl. ``hitl_pending``)."""
    stub()


@router.get("/{return_id}", response_model=Envelope[ReturnOut], summary="Get a return")
def get_return(return_id: str) -> Envelope[ReturnOut]:
    """Single return detail."""
    stub()


@router.patch(
    "/{return_id}",
    response_model=Envelope[ReturnOut],
    summary="Decide a return (support/admin/HITL)",
)
def decide_return(return_id: str, body: ReturnDecision) -> Envelope[ReturnOut]:
    """Approve / reject / refund a return. The HITL resolution path. (J-SUP-03)"""
    stub()
