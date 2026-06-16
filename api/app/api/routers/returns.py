"""Return read + decision routes (US-E6 / J-SUP-03).

Request-a-return lives under ``/orders/{id}/returns`` (orders router). These are the
list/get + the support/admin (or HITL) decision endpoints. Thin handlers over
``app.services.returns``; the within-window policy + refund reuse live in the service.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api._contract import ERROR_RESPONSES
from app.api.deps import CurrentUser, SessionDep
from app.schemas.envelope import Envelope, ListEnvelope
from app.schemas.returns import ReturnDecision, ReturnOut
from app.services import returns as returns_service

router = APIRouter(prefix="/returns", tags=["returns"], responses=ERROR_RESPONSES)


@router.get("", response_model=ListEnvelope[ReturnOut], summary="List returns")
def list_returns(
    user: CurrentUser,
    session: SessionDep,
    status_filter: str | None = Query(default=None, alias="status"),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> ListEnvelope[ReturnOut]:
    """Buyer sees own returns; support/admin can filter all (incl. ``hitl_pending``)."""
    return returns_service.list_returns(
        session, user, status_filter=status_filter, cursor=cursor, limit=limit
    )


@router.get("/{return_id}", response_model=Envelope[ReturnOut], summary="Get a return")
def get_return(
    return_id: str, user: CurrentUser, session: SessionDep
) -> Envelope[ReturnOut]:
    """Single return detail (owner or support/admin; 404 no-leak otherwise)."""
    return Envelope(data=returns_service.get_return(session, user, return_id))


@router.patch(
    "/{return_id}",
    response_model=Envelope[ReturnOut],
    summary="Decide a return (support/admin/HITL)",
)
def decide_return(
    return_id: str, body: ReturnDecision, user: CurrentUser, session: SessionDep
) -> Envelope[ReturnOut]:
    """Approve / reject / refund a return. The HITL resolution path. (J-SUP-03)"""
    return Envelope(data=returns_service.decide_return(session, user, return_id, body))
