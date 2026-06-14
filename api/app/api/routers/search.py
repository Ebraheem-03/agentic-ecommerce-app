"""Search route — keyword retrieval LIVE; semantic/hybrid plug in later (Echo, US-E4-07).

``GET /search`` runs catalog keyword search (Postgres full-text, ``ts_rank``) over the
seeded catalog and returns the contract-v0 ``{data, meta}`` envelope: ``data`` is a list
of ``SearchResult`` (each a ``ProductSummary`` + a relevance ``score``) and ``meta`` is a
``SearchMeta`` carrying the retrieval ``mode`` discriminator (``keyword`` today). So
semantic/pgvector retrieval drops in behind the SAME shape — only ``mode`` changes — with
no contract change (contract-v0 Decision-4).

The retriever/rerank seam lives in ``app.services.search``; this router stays thin.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api._contract import ERROR_RESPONSES
from app.api.deps import SessionDep
from app.schemas.search import SearchEnvelope
from app.services import search as search_service

router = APIRouter(tags=["search"], responses=ERROR_RESPONSES)


@router.get(
    "/search",
    response_model=SearchEnvelope,
    summary="Search products (keyword live; semantic later)",
)
def search(
    session: SessionDep,
    q: str = Query(min_length=1, max_length=200, description="Search query."),
    category: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=24, ge=1, le=100),
) -> SearchEnvelope:
    """Catalog search; relevance ``mode`` + per-result ``score`` reported. (J-BUY-01)"""
    return search_service.search_products(
        session, q=q, category=category, cursor=cursor, limit=limit
    )
