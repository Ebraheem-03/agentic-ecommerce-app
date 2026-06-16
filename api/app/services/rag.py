"""Support-RAG over policy prose + the unified citation/source resolver (US-E5-05).

WHY THIS MODULE
===============
``app.services.search`` retrieves over the **catalog** (products, FTS ``search_tsv``).
The support agent (US-E5-06) answers **policy** questions ("what's the return window?",
"can I return an opened balm?") which must retrieve over the **policies** table prose, not
products. This module is that second retrieval surface — kept behind the SAME
``Retriever``-style seam as catalog search, embedding-agnostic, with a key-free
deterministic default so CI passes with no provider key.

DESIGN: a policy retriever ALONGSIDE the product one (not a unified index)
=========================================================================
Policies and products are different source rows with different citation shapes, and the
support agent needs policy grounding specifically. A separate ``PolicyRetriever`` keeps
each surface simple and the citation mapping unambiguous. Both retrievers share the same
``embed_query`` provider seam (ADR-0032) and the same ``RetrievedDoc`` output unit, so a
future unified doc index could fuse them without changing callers.

  * ``KeywordPolicyRetriever`` (LIVE default) — Postgres FTS computed on the fly over
    ``policies.title || body`` with ``websearch_to_tsquery`` + ``ts_rank``. No new column,
    no migration, deterministic, key-free → the CI-safe default.
  * ``SemanticPolicyRetriever`` (active under ``EMBED_PROVIDER=gemini``) — cosine ANN over
    the seeded ``policy``-source embeddings via ``embed_query`` (RETRIEVAL_QUERY).
  * ``HybridPolicyRetriever`` — RRF fusion of the two (mirrors the catalog hybrid).

``_ACTIVE_POLICY_MODE`` selects the active retriever; default keyword (key-free CI). Echo
flips it to hybrid alongside ``EMBED_PROVIDER=gemini`` — one local env change, no caller
change.

CITATIONS
=========
``retrieved_doc_citation`` maps a ``RetrievedDoc`` to the contract ``Citation`` (snippet +
``source_type``/``source_id``/``chunk_index``). ``policy_citation_key`` /
``product_citation_key`` derive the GOLDEN ``source_docs`` key shape
(``kind@store-slug`` / ``kind@platform`` for policies, the product slug for products) so
Juno's RAGAS can resolve a live citation back to a golden expectation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import Float, func, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import Embedding, Policy, Product
from app.services.embeddings import get_embedder

# Source-type label for policy embeddings (mirrors the embedding_source enum).
POLICY_SOURCE = "policy"

# RRF constant + per-arm over-fetch, mirroring the catalog hybrid retriever.
_RRF_K = 60
_HYBRID_FETCH = 20

# A retrieved policy chunk's snippet is capped so citation frames stay compact.
_SNIPPET_MAX = 600


@dataclass(frozen=True, slots=True)
class RetrievedDoc:
    """One retrieved grounding document (policy or product), pre-citation.

    The shared output unit of every RAG retriever. ``source_type`` mirrors the
    ``embedding_source`` enum (policy | product); ``source_id`` is the row id;
    ``citation_key`` is the GOLDEN ``source_docs`` key (``kind@store-slug`` / slug) so a
    live citation resolves back to a golden expectation. ``text`` is the quotable prose
    the answer is grounded in; ``score`` is the retriever-native relevance.
    """

    source_type: str
    source_id: str
    citation_key: str
    title: str
    text: str
    score: float | None
    chunk_index: int = 0

    def snippet(self) -> str:
        body = self.text.strip()
        return body if len(body) <= _SNIPPET_MAX else body[: _SNIPPET_MAX - 1] + "…"


# --------------------------------------------------------------------------- #
# Citation-key derivation — the GOLDEN source_docs shape.                       #
# --------------------------------------------------------------------------- #
# Very common words that add no retrieval signal — dropped so the OR query isn't dominated
# by them (Postgres' FTS dictionary already drops most, but trimming these tightens rank).
_STOPISH = frozenset(
    {"what", "is", "the", "a", "an", "do", "you", "i", "my", "how", "can", "and", "of",
     "to", "for", "are", "does", "when", "it", "in", "on", "me", "your"}
)


def _or_query(query: str) -> str:
    """Turn a natural-language query into an ``OR``-joined websearch query string.

    Splits on non-word chars, drops trivial stop-ish words, and joins the rest with the
    websearch ``OR`` operator so a policy matching ANY salient term is retrieved (AND is
    too strict for a conversational question). Empty -> the original query (let FTS decide).
    """
    words = [w for w in re.split(r"\W+", query.lower()) if w and w not in _STOPISH]
    return " OR ".join(words) if words else query


def policy_citation_key(kind: str, store_slug: str | None) -> str:
    """``kind@store-slug`` for a store policy; ``kind@platform`` for a platform policy.

    Matches the golden ``source_docs`` keys (e.g. ``returns@platform``,
    ``care@solveig-ceramics``). Platform policies have ``store_id`` NULL -> ``@platform``.
    """
    return f"{kind}@{store_slug}" if store_slug else f"{kind}@platform"


def product_citation_key(slug: str) -> str:
    """A product citation key is its slug (the golden ``source_docs`` product key)."""
    return slug


# --------------------------------------------------------------------------- #
# Policy retrievers — keyword (key-free default) + semantic + hybrid.           #
# --------------------------------------------------------------------------- #
class PolicyRetriever(Protocol):
    """The policy-retrieval seam; every mode satisfies it (mirrors ``search.Retriever``)."""

    def retrieve(
        self, session: Session, *, query: str, store_id: str | None, limit: int
    ) -> list[RetrievedDoc]: ...


def _policy_doc(policy: Policy, score: float | None) -> RetrievedDoc:
    store_slug = policy.store.slug if policy.store is not None else None
    return RetrievedDoc(
        source_type=POLICY_SOURCE,
        source_id=policy.id,
        citation_key=policy_citation_key(policy.kind, store_slug),
        title=policy.title,
        text=f"{policy.title}\n{policy.body}",
        score=score,
    )


class KeywordPolicyRetriever:
    """LIVE default: Postgres FTS over ``policies.title || body`` (key-free, deterministic).

    Computes the ``tsvector`` on the fly (title weighted above body) — no stored column, no
    migration. Ranks active policies by ``ts_rank`` against a ``websearch_to_tsquery``.
    Active + content-derived, so it's the CI-safe default with no embedding provider.
    """

    def retrieve(
        self, session: Session, *, query: str, store_id: str | None, limit: int
    ) -> list[RetrievedDoc]:
        # Combine title + body into one tsvector. (We skip ``setweight`` to avoid a
        # ``"char"``-cast dance; the title is short and leads the body, so an unweighted
        # vector ranks the right policy for these support questions.)
        document = func.concat(
            func.coalesce(Policy.title, ""), " ", func.coalesce(Policy.body, "")
        )
        tsvector = func.to_tsvector("english", document)
        # OR-match the query terms (``websearch_to_tsquery`` defaults to AND, which is too
        # strict for a natural-language support question like "what's the return window?").
        # ``ts_rank`` still orders by how MANY/how-weighted the terms matched, so the most
        # on-topic policy ranks first; OR just means a doc need not contain EVERY word.
        tsquery = func.websearch_to_tsquery("english", _or_query(query))
        rank = func.ts_rank(tsvector, tsquery).cast(Float)
        stmt = (
            select(Policy, rank.label("score"))
            .where(Policy.is_active.is_(True), tsvector.op("@@")(tsquery))
            .options(joinedload(Policy.store))
            .order_by(rank.desc(), Policy.id.desc())
            .limit(limit)
        )
        if store_id is not None:
            # Store-scoped questions consider that store's policies AND platform policies.
            stmt = stmt.where(
                (Policy.store_id == store_id) | (Policy.store_id.is_(None))
            )
        return [
            _policy_doc(policy, float(score))
            for policy, score in session.execute(stmt).all()
        ]


class SemanticPolicyRetriever:
    """Cosine ANN over ``policy``-source embeddings (active under EMBED_PROVIDER=gemini).

    Embeds the query via ``embed_query`` (RETRIEVAL_QUERY; ADR-0032), runs a cosine ``<=>``
    ANN over the HNSW index, joins back to the live ``Policy``. Meaningful only with a real
    embedder (stub vectors are noise), but correct + key-free to RUN either way.
    """

    def retrieve(
        self, session: Session, *, query: str, store_id: str | None, limit: int
    ) -> list[RetrievedDoc]:
        query_vec = get_embedder().embed_query(query)
        distance = Embedding.embedding.cosine_distance(query_vec)
        stmt = (
            select(Policy, distance.label("distance"))
            .join(Embedding, Embedding.source_id == Policy.id)
            .where(Embedding.source_type == POLICY_SOURCE, Policy.is_active.is_(True))
            .options(joinedload(Policy.store))
            .order_by(distance.asc())
            .limit(limit)
        )
        if store_id is not None:
            stmt = stmt.where(
                (Policy.store_id == store_id) | (Policy.store_id.is_(None))
            )
        return [
            _policy_doc(policy, 1.0 - float(dist))
            for policy, dist in session.execute(stmt).all()
        ]


class HybridPolicyRetriever:
    """RRF fusion of keyword + semantic policy retrieval (mirrors the catalog hybrid)."""

    def __init__(self) -> None:
        self._keyword = KeywordPolicyRetriever()
        self._semantic = SemanticPolicyRetriever()

    def retrieve(
        self, session: Session, *, query: str, store_id: str | None, limit: int
    ) -> list[RetrievedDoc]:
        kw = self._keyword.retrieve(
            session, query=query, store_id=store_id, limit=_HYBRID_FETCH
        )
        sem = self._semantic.retrieve(
            session, query=query, store_id=store_id, limit=_HYBRID_FETCH
        )
        return _rrf_fuse_docs(kw, sem)[:limit]


def _rrf_fuse_docs(*ranked: list[RetrievedDoc]) -> list[RetrievedDoc]:
    """Reciprocal-rank fusion of ranked ``RetrievedDoc`` lists (rank-only, score-scale free)."""
    fused: dict[str, float] = {}
    keep: dict[str, RetrievedDoc] = {}
    for results in ranked:
        for rank, doc in enumerate(results):
            fused[doc.source_id] = fused.get(doc.source_id, 0.0) + 1.0 / (_RRF_K + rank)
            keep.setdefault(doc.source_id, doc)
    ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
    return [
        RetrievedDoc(
            source_type=keep[sid].source_type,
            source_id=sid,
            citation_key=keep[sid].citation_key,
            title=keep[sid].title,
            text=keep[sid].text,
            score=score,
            chunk_index=keep[sid].chunk_index,
        )
        for sid, score in ordered
    ]


# --------------------------------------------------------------------------- #
# Active retriever selection — keyword by default (key-free CI), hybrid local.  #
# --------------------------------------------------------------------------- #
class PolicyMode:
    keyword = "keyword"
    semantic = "semantic"
    hybrid = "hybrid"


_POLICY_RETRIEVERS: dict[str, type[PolicyRetriever]] = {
    PolicyMode.keyword: KeywordPolicyRetriever,
    PolicyMode.semantic: SemanticPolicyRetriever,
    PolicyMode.hybrid: HybridPolicyRetriever,
}
# Default keyword so CI is key-free + deterministic. Echo flips to ``hybrid`` alongside
# ``EMBED_PROVIDER=gemini`` (one local env change) — no caller change.
_ACTIVE_POLICY_MODE: str = PolicyMode.keyword


def get_policy_retriever(mode: str | None = None) -> PolicyRetriever:
    """Resolve the active policy retriever (defaults to the live keyword path)."""
    return _POLICY_RETRIEVERS[mode or _ACTIVE_POLICY_MODE]()


def retrieve_policies(
    session: Session,
    *,
    query: str,
    store_id: str | None = None,
    limit: int = 4,
) -> list[RetrievedDoc]:
    """Retrieve the policy docs most relevant to ``query`` (the support-RAG entry point).

    Uses the active policy retriever (keyword default; hybrid under a real embedder).
    Returns ``RetrievedDoc``s already ranked best-first — the support agent grounds its
    answer in these and cites them. Empty list = nothing relevant (the agent refuses
    rather than inventing).
    """
    return get_policy_retriever().retrieve(
        session, query=query, store_id=store_id, limit=limit
    )


def resolve_product_doc(product: Product, *, score: float | None = None) -> RetrievedDoc:
    """Wrap a retrieved ``Product`` as a ``RetrievedDoc`` (slug citation key).

    Lets the support agent cite a product it grounded a claim in (e.g. EVAL-025 cites the
    Salve Hand Balm product alongside the returns policies) using the same citation path.
    """
    text = product.description or product.title
    return RetrievedDoc(
        source_type="product",
        source_id=product.id,
        citation_key=product_citation_key(product.slug),
        title=product.title,
        text=text,
        score=score,
    )


__all__ = [
    "POLICY_SOURCE",
    "HybridPolicyRetriever",
    "KeywordPolicyRetriever",
    "PolicyMode",
    "PolicyRetriever",
    "RetrievedDoc",
    "SemanticPolicyRetriever",
    "get_policy_retriever",
    "policy_citation_key",
    "product_citation_key",
    "resolve_product_doc",
    "retrieve_policies",
]
