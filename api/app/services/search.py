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

from app.db.models import Embedding, Product
from app.schemas.search import (
    SearchEnvelope,
    SearchMeta,
    SearchMode,
    SearchResult,
)
from app.services.catalog import _ACTIVE, _eager_product, _product_summary
from app.services.embeddings import PRODUCT_SOURCE, get_embedder

# How many candidates each arm of the hybrid retriever fetches before fusion. A small
# over-fetch (vs. the final ``limit``) gives reciprocal-rank fusion something to fuse.
_HYBRID_FETCH = 50

# Reciprocal-rank-fusion constant (the standard k=60). Dampens the contribution of
# low-ranked items so a doc ranked highly by EITHER arm still surfaces.
_RRF_K = 60

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
    """LIVE (US-E5-05): pgvector cosine ANN retrieval over the ``embeddings`` table.

    Embeds the query with ``get_embedder().embed_query`` — the RETRIEVAL_QUERY task path
    (asymmetric retrieval; ADR-0032), NOT ``embed_text`` — then runs a cosine ``<=>`` ANN
    search against the HNSW ``vector_cosine_ops`` index over product-source embeddings,
    joining back to the live ``Product`` so the result unit is the same ``ScoredProduct``
    as ``KeywordRetriever`` (``score`` = cosine similarity in [0, 1]).

    With the default ``StubEmbedder`` the cosine geometry is meaningless (stub vectors are
    content-hash noise), so this branch is only meaningful under ``EMBED_PROVIDER=gemini``.
    It is correct + key-free to RUN either way (no live call from the stub) — it just isn't
    the active mode by default, so CI never depends on its ranking quality.
    """

    mode = SearchMode.semantic

    def retrieve(
        self, session: Session, *, query: str, category: str | None, limit: int
    ) -> list[ScoredProduct]:
        return _semantic_products(session, query=query, category=category, limit=limit)


class HybridRetriever:
    """LIVE (US-E5-05): fuse keyword + semantic with reciprocal-rank fusion, then rerank.

    Runs both ``KeywordRetriever`` (FTS/ts_rank) and ``SemanticRetriever`` (cosine ANN),
    over-fetches from each, fuses their rank orders via RRF (rank-only, so the two
    incomparable score scales never need normalizing), then passes the fused list through
    ``rerank()``. Reports ``mode = hybrid``. The keyword half is meaningful even on the
    stub embedder, so hybrid degrades gracefully to keyword-dominant ranking when no real
    embeddings are present.
    """

    mode = SearchMode.hybrid

    def __init__(self) -> None:
        self._keyword = KeywordRetriever()
        self._semantic = SemanticRetriever()

    def retrieve(
        self, session: Session, *, query: str, category: str | None, limit: int
    ) -> list[ScoredProduct]:
        kw = self._keyword.retrieve(
            session, query=query, category=category, limit=_HYBRID_FETCH
        )
        sem = self._semantic.retrieve(
            session, query=query, category=category, limit=_HYBRID_FETCH
        )
        fused = _rrf_fuse(kw, sem)
        return fused[:limit]


def _semantic_products(
    session: Session, *, query: str, category: str | None, limit: int
) -> list[ScoredProduct]:
    """Cosine ANN over product embeddings -> ScoredProduct list (similarity as score)."""
    query_vec = get_embedder().embed_query(query)
    distance = Embedding.embedding.cosine_distance(query_vec)
    stmt = (
        select(Product, distance.label("distance"))
        .join(Embedding, Embedding.source_id == Product.id)
        .where(
            Embedding.source_type == PRODUCT_SOURCE,
            Product.status == _ACTIVE,
            Product.deleted_at.is_(None),
        )
        .options(*_eager_product())
        .order_by(distance.asc())
        .limit(limit)
    )
    if category is not None:
        stmt = stmt.where(Product.category == category)
    return [
        # cosine_distance is 1 - cosine_similarity; convert to a [0,1] similarity score.
        ScoredProduct(product=product, score=1.0 - float(dist))
        for product, dist in session.execute(stmt).all()
    ]


def _rrf_fuse(*ranked: list[ScoredProduct]) -> list[ScoredProduct]:
    """Reciprocal-rank fusion of several ranked ScoredProduct lists, best-first.

    RRF scores each product by ``sum(1 / (k + rank))`` across the lists it appears in
    (rank is 0-based per list). Rank-only fusion sidesteps the incomparable ts_rank vs.
    cosine score scales. The product instance from the first list it appears in is kept;
    its ``score`` is set to the fused RRF score so the route still surfaces a relevance.
    """
    fused: dict[str, float] = {}
    keep: dict[str, ScoredProduct] = {}
    for results in ranked:
        for rank, sp in enumerate(results):
            pid = sp.product.id
            fused[pid] = fused.get(pid, 0.0) + 1.0 / (_RRF_K + rank)
            keep.setdefault(pid, sp)
    ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
    return [ScoredProduct(product=keep[pid].product, score=score) for pid, score in ordered]


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
    """Rerank — IDENTITY passthrough for v0 (US-E4-07 seam, kept by US-E5-05).

    For the hybrid path the relevance signal is already the reciprocal-rank fusion of two
    independent retrievers (FTS + cosine ANN), which is a strong first pass; a second-stage
    reranker only earns its place at larger candidate counts than this catalog has. So v0
    stays identity and the fused order is authoritative.

    Where a real reranker slots: a cross-encoder (e.g. ``BAAI/bge-reranker`` via a local
    ONNX/sentence-transformers session, or a hosted rerank endpoint) would score each
    ``(query, product-document)`` pair and re-sort here — the call site is unchanged. It is
    deliberately NOT wired now: it needs model weights in the image (breaking the key-free
    CI constraint unless run behind the same ``EMBED_PROVIDER``-style seam) and buys little
    over RRF on a single-digit-result catalog. This is documented as the v0 trade-off.
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
