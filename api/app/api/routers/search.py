"""Search route (contract draft). v0 keyword; semantic plugs in later (Echo)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api._contract import ERROR_RESPONSES, stub
from app.schemas.envelope import ListEnvelope
from app.schemas.search import SearchResult

router = APIRouter(tags=["search"], responses=ERROR_RESPONSES)


@router.get(
    "/search",
    response_model=ListEnvelope[SearchResult],
    summary="Search products (keyword v0; semantic later)",
)
def search(
    q: str = Query(min_length=1, max_length=200, description="Search query."),
    category: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=24, ge=1, le=100),
) -> ListEnvelope[SearchResult]:
    """Catalog search. Retrieval mode is reported per response. (J-BUY-01)"""
    stub()
