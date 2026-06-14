"""Search request/response.

v0 is keyword search over the catalog (title/description/category). The response
shape is retrieval-mode agnostic so semantic/pgvector retrieval (Echo, Week-4) can
plug in WITHOUT changing the contract — we expose a per-result ``score`` and a
``mode`` discriminator (carried in the list ``meta``). We do NOT bake an embedding
dimension here.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.catalog import ProductSummary
from app.schemas.envelope import CamelModel, PageMeta


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


class SearchMeta(PageMeta):
    """List meta for GET /search: the page meta plus the retrieval discriminator.

    Carries ``mode`` (``SearchMode``) alongside the standard cursor/limit/total so the
    client/agent knows which retrieval path served the page. Semantic/pgvector retrieval
    (Echo, Week-4) reuses this exact shape — it only changes the ``mode`` value, never the
    contract (contract-v0 Decision-4).
    """

    mode: SearchMode = Field(
        default=SearchMode.keyword,
        description="Retrieval path that served these results (keyword v0).",
    )


class SearchEnvelope(BaseModel):
    """Success envelope for GET /search: ``{data: SearchResult[], meta: SearchMeta}``.

    Mirrors the generic ``ListEnvelope`` but pins ``meta`` to ``SearchMeta`` so the
    retrieval ``mode`` discriminator surfaces in the response. Keeping the ``{data, meta}``
    shape means semantic/hybrid retrieval is a ``mode``-value change, not a contract change.
    """

    model_config = ConfigDict(extra="forbid")

    data: list[SearchResult]
    meta: SearchMeta
