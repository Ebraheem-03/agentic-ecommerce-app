"""Catalog search — keyword retrieval LIVE + semantic/hybrid seam + rerank stub (US-E4-07).

CONTRACT FRAME (contract-v0 Decision-4)
=======================================
Keyword search is the LIVE retrieval path over the seeded catalog. pgvector/semantic
retrieval is DEFERRED to Echo (Week-4) and MUST drop in behind the SAME response shape
with NO contract change. The response already carries everything semantic needs:

  * a top-level ``mode`` discriminator (``SearchMode``: keyword | semantic | hybrid), and
  * a per-result ``score`` (the ranked relevance; ``ts_rank`` for keyword today).

So the seam below is structural, not behavioural: a ``Retriever`` Protocol with a live
``KeywordRetriever`` and stubbed ``SemanticRetriever`` / ``HybridRetriever``, plus an
identity ``rerank()``. When Echo flips ``EMBED_PROVIDER`` to a real model and selects the
semantic/hybrid branch, the SAME endpoint/response serves ranked hybrid results.

KEYWORD RELEVANCE
=================
We use Postgres full-text search, not naive ILIKE: the ``products.search_tsv`` generated
``tsvector`` (migration 0005, title>category>description weighting) matched with
``websearch_to_tsquery('english', q)`` and ordered by ``ts_rank`` as the ``score``. This
makes a query for a distinctive seed term rank the right product first.

PAGINATION
==========
Keyword results are ranked, not time-ordered, so the shared keyset ``(created_at, id)``
cursor (used by catalog list) does not apply — a relevance sort has no monotonic key to
key off. v0 returns a single ranked page (``next_cursor = None``) capped at ``limit``;
the ranked-cursor design is deferred with semantic retrieval (documented in ADR-0027).
The response shape is identical, so adding a ranked cursor later is non-breaking.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import Float, func, select
from sqlalchemy.orm import Session

from app.db.models import Product
from app.schemas.search import (
    SearchEnvelope,
    SearchMeta,
    SearchMode,
    SearchResult,
)
from app.services.catalog import _ACTIVE, _eager_product, _product_summary

# A single ranked page is returned for v0 keyword search (no ranked cursor yet — see
# module docstring). The route still enforces the contract limit (1..100); this is the
# hard upper bound on rows scored per query.
_MAX_RESULTS = 100


class ScoredProduct:
    """One retrieved product plus its relevance score (pre-projection).

    The retriever's output unit. ``score`` is the retriever-native relevance (``ts_rank``
    for keyword; cosine similarity / fused score for semantic/hybrid later). ``rerank()``
    consumes a list of these; the route projects each ``Product`` to a ``ProductSummary``.
    """

    __slots__ = ("product", "score")

    def __init__(self, product: Product, score: float | None) -> None:
        self.product = product
        self.score = score


class Retriever(Protocol):
    """The retrieval seam. Every mode (keyword live; semantic/hybrid later) satisfies it.

    ``retrieve`` returns products already ranked best-first with a per-item ``score``.
    ``mode`` is the discriminator written into ``SearchResponse.mode`` so the client/agent
    knows which path served the results — the whole point of Decision-4's no-change swap.
    """

    @property
    def mode(self) -> SearchMode: ...

    def retrieve(
        self, session: Session, *, query: str, category: str | None, limit: int
    ) -> list[ScoredProduct]: ...


class KeywordRetriever:
    """LIVE retriever: Postgres full-text search over ``products.search_tsv`` (ts_rank).

    Builds a ``websearch_to_tsquery`` from the user's query (so quoted phrases / OR / -term
    work naturally), matches active, non-deleted products with ``@@``, and orders by
    ``ts_rank`` descending (the per-result ``score``), id as a deterministic tiebreaker.
    Eager-loads the projection's relationships so result rows never N+1.
    """

    mode = SearchMode.keyword

    def retrieve(
        self, session: Session, *, query: str, category: str | None, limit: int
    ) -> list[ScoredProduct]:
        tsquery = func.websearch_to_tsquery("english", query)
        rank = func.ts_rank(Product.search_tsv, tsquery).cast(Float)
        stmt = (
            select(Product, rank.label("score"))
            .where(
                Product.status == _ACTIVE,
                Product.deleted_at.is_(None),
                Product.search_tsv.op("@@")(tsquery),
            )
            .options(*_eager_product())
            .order_by(rank.desc(), Product.id.desc())
            .limit(limit)
        )
        if category is not None:
            stmt = stmt.where(Product.category == category)
        return [
            ScoredProduct(product=product, score=float(score))
            for product, score in session.execute(stmt).all()
        ]


class SemanticRetriever:
    """SEAM (deferred to Echo, Week-4): pgvector ANN retrieval over ``embeddings``.

    NOT the live path — contract-v0 Decision-4 defers real semantic retrieval to Echo.
    It exists so the structure is in place: Echo embeds the query via ``get_embedder()``
    (the US-E4-08 provider seam), runs a cosine ``<=>`` ANN search against the HNSW index,
    and returns ``ScoredProduct``s with cosine similarity as ``score`` — same output unit
    as ``KeywordRetriever``, so the route and response are unchanged.

    Today it is inert: it raises if selected, so flipping it on is a deliberate Echo act,
    never a silent default. ``get_embedder()`` is intentionally referenced (not called) to
    pin the wiring point.
    """

    mode = SearchMode.semantic

    def retrieve(
        self, session: Session, *, query: str, category: str | None, limit: int
    ) -> list[ScoredProduct]:
        raise NotImplementedError(
            "Semantic retrieval is deferred to Echo (Week-4, contract-v0 Decision-4). "
            "Wire it here: embed `query` via app.services.embeddings.get_embedder(), run "
            "a cosine ANN search over embeddings.embedding, return ScoredProduct list."
        )


class HybridRetriever:
    """SEAM (deferred to Echo, Week-4): fuse keyword + semantic, then rerank.

    The intended live path once a real embedder lands: run both ``KeywordRetriever`` and
    ``SemanticRetriever``, fuse their scored lists (e.g. reciprocal-rank fusion), then pass
    through ``rerank()``. Reports ``mode = hybrid``. Inert today for the same reason as
    ``SemanticRetriever``; the keyword half already works, so enabling hybrid is additive.
    """

    mode = SearchMode.hybrid

    def __init__(self) -> None:
        self._keyword = KeywordRetriever()
        self._semantic = SemanticRetriever()

    def retrieve(
        self, session: Session, *, query: str, category: str | None, limit: int
    ) -> list[ScoredProduct]:
        raise NotImplementedError(
            "Hybrid retrieval is deferred to Echo (Week-4). Fuse KeywordRetriever + "
            "SemanticRetriever (e.g. RRF), then pass through rerank()."
        )


# The active retriever. Keyword is the only live path (Decision-4); the semantic/hybrid
# seams are registered so Echo selects one by swapping this single reference (and, for
# semantic, flipping EMBED_PROVIDER to a real model) — no route or schema change.
_RETRIEVERS: dict[SearchMode, type[Retriever]] = {
    SearchMode.keyword: KeywordRetriever,
    SearchMode.semantic: SemanticRetriever,
    SearchMode.hybrid: HybridRetriever,
}
_ACTIVE_MODE: SearchMode = SearchMode.keyword


def get_retriever(mode: SearchMode | None = None) -> Retriever:
    """Resolve the active retriever (defaults to the live keyword path)."""
    return _RETRIEVERS[mode or _ACTIVE_MODE]()


def rerank(results: list[ScoredProduct], *, query: str) -> list[ScoredProduct]:
    """Rerank stub — IDENTITY passthrough today (US-E4-07).

    The seam where Echo plugs a cross-encoder / LLM reranker (Week-4): reorder the
    retrieved candidates by a stronger relevance signal than the retriever's first-pass
    score. Today it returns the list unchanged so the keyword ranking is authoritative,
    and the call site never changes when a real reranker lands.
    """
    return results


def search_products(
    session: Session,
    *,
    q: str,
    category: str | None,
    cursor: str | None,
    limit: int,
) -> SearchEnvelope:
    """Run catalog search and return the ``{data, meta}`` search envelope.

    Keyword retrieval is live (ts_rank over the FTS column); ``rerank()`` is identity
    today. Returns a single ranked page — relevance ordering has no keyset, so
    ``next_cursor`` is null in v0 (a ranked cursor is deferred with semantic retrieval).
    No matches -> empty ``data`` (a 200, not a 404). ``meta.mode`` is the live retriever's
    discriminator (keyword today). ``cursor`` is accepted for forward-compatibility but
    not yet honored (no ranked cursor in v0).
    """
    _ = cursor  # reserved; ranked cursor deferred with semantic retrieval (ADR-0027)
    retriever = get_retriever()
    page_size = min(limit, _MAX_RESULTS)
    scored = retriever.retrieve(session, query=q, category=category, limit=page_size)
    scored = rerank(scored, query=q)
    data = [
        SearchResult(product=_product_summary(sp.product), score=sp.score)
        for sp in scored
    ]
    return SearchEnvelope(
        data=data,
        meta=SearchMeta(
            next_cursor=None, limit=limit, total=len(data), mode=retriever.mode
        ),
    )
