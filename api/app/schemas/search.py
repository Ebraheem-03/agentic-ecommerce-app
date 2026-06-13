"""Search request/response.

v0 is keyword search over the catalog (title/description/category). The response
shape is retrieval-mode agnostic so semantic/pgvector retrieval (Echo, Week-2) can
plug in WITHOUT changing the contract — we expose a per-result ``score`` and a
top-level ``mode`` discriminator. We do NOT bake an embedding dimension here.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from app.schemas.catalog import ProductSummary
from app.schemas.envelope import CamelModel


class SearchMode(StrEnum):
    keyword = "keyword"
    semantic = "semantic"
    hybrid = "hybrid"


class SearchResult(CamelModel):
    """A product plus an optional relevance score (null for pure keyword v0)."""

    product: ProductSummary
    score: float | None = Field(
        default=None,
        description="Relevance score when a ranked retriever is used; null for v0 keyword.",
    )


class SearchResponse(CamelModel):
    """Body of GET /search. Wrapped in ListEnvelope[SearchResult] at the route."""

    mode: SearchMode = SearchMode.keyword
    query: str
