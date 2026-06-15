"""Semantic cache — non-personalized LLM-response memoization (US-E5-09, ADR-0034 §2).

A pgvector-backed cache so repeated/similar NON-PERSONALIZED prompts skip the LLM
round-trip. The value is CROSS-USER sharing: an entry created by any user accelerates
every later user asking a semantically-similar question — exactly the high-volume,
high-overlap surface (intent classification fires every turn; policy/FAQ questions repeat
across thousands of users).

WHAT IS CACHEABLE (the allow-list, ADR-0034 §2)
===============================================
ONLY tenant-shared, non-personalized calls:
  * ``CLASSIFY`` — intent classification (raw utterance + fixed system prompt; no identity,
    no PII). The primary, every-turn win. Global namespace (no ``store_id``).
  * ``POLICY``   — grounded policy-RAG answers, keyed on shared policy docs. STORE-SCOPED
    (``store_id`` in the namespace) so a store-A shopper is never served a store-B answer.

NEVER cached (enforced by the CALLERS, not here): the shopping node / any tool-result /
order / cart / payment / PII / refusals / HITL / any turn where ``scan_for_injection``
fired. This module only ever stores what a caller hands it, and a caller hands it only an
allow-listed success — never an ``APIError`` (cache successes only).

ORDERING (load-bearing, ADR-0033)
=================================
Per turn the caller's order is ``scan_for_injection -> cache_lookup -> brain/LLM ->
cache_store``. The cache must NEVER sit ahead of the injection scan: a paraphrased
malicious prompt that collided with a cached benign one would otherwise skip injection
defense and the audit row. ``cache_lookup`` therefore assumes the scan already passed.

KEY COMPOSITION
===============
A hit must share the namespace ``(node_type, provider, model, embed_provider, embed_dim
[, store_id])`` — a provider/dim swap must not serve vectors from a different space, and
``node_type`` namespacing means a shopping prompt can never resolve a support entry. Within
a namespace:
  * real embedder (``EMBED_PROVIDER=gemini``): a cosine ``query_embedding`` neighbour at or
    above ``SEMANTIC_CACHE_THRESHOLD`` (0.95 — a paraphrase, not a topic match);
  * stub embedder (CI default): the embedding similarity is NOISE, so fall back to an EXACT
    normalized-prompt match (the cache can't mis-hit).

INVALIDATION
============
Content-version is primary, TTL is the backstop. ``cache_store`` records the grounding
``source_ids`` + a ``content_version`` (e.g. the policy rows' max ``updated_at``/``version``);
``cache_lookup`` only returns an entry whose ``content_version`` still matches what the
caller computed now — so a policy edit busts stale entries. ``expires_at`` (classifier 24h,
policy 1h) is the time backstop.

DEGRADATION
===========
The cache is an OPTIMIZATION. Any lookup/store failure is swallowed and logged — a lookup
miss/error degrades to a live LLM call, a store error is a no-op; neither ever surfaces as
``internal_error`` to the caller.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import SemanticCacheEntry
from app.services.embeddings import get_embedder

_log = logging.getLogger(__name__)

# The stub embedder's model tag (its vectors are content-hash noise -> exact-match tier).
_STUB_EMBED_PROVIDER = "stub"


class CacheNodeType(StrEnum):
    """The cacheable, non-personalized node surfaces (ADR-0034 §2 allow-list)."""

    classify = "classify"
    policy = "policy"


@dataclass(frozen=True, slots=True)
class CacheKey:
    """The non-content half of a cache entry's identity — its namespace.

    A hit must match ALL of these. ``store_id`` is None for the global classifier cache and
    the owning store id for the store-scoped policy cache. ``provider``/``model`` are the
    runtime LLM that produced the cached response; ``embed_provider``/``embed_dim`` pin the
    vector space so a provider/dim swap never serves a stale-space neighbour.
    """

    node_type: CacheNodeType
    provider: str
    model: str
    embed_provider: str
    embed_dim: int
    store_id: str | None = None


def runtime_cache_key(
    node_type: CacheNodeType, *, store_id: str | None = None
) -> CacheKey:
    """Build the namespace key from the live runtime config (the common caller path)."""
    return CacheKey(
        node_type=node_type,
        provider=settings.llm_provider,
        model=_runtime_model(),
        embed_provider=settings.embed_provider,
        embed_dim=settings.embed_dim,
        store_id=store_id,
    )


def _runtime_model() -> str:
    """The model name for the active runtime provider (mirrors get_chat_model's choice)."""
    if settings.llm_provider == "gemini":
        return settings.gemini_model
    return settings.groq_model


def normalize_prompt(text: str) -> str:
    """Canonicalize a prompt for the exact-match tier + stable storage.

    Lowercase, collapse whitespace, strip. Deterministic so the stub exact-match tier and
    the stored ``norm_prompt`` agree. (Semantic paraphrase matching is the embedding tier's
    job under a real embedder; this is only the floor.)
    """
    return re.sub(r"\s+", " ", text.strip().lower())


def _is_stub_embedder() -> bool:
    return settings.embed_provider == _STUB_EMBED_PROVIDER


def _ttl_for(node_type: CacheNodeType) -> int:
    if node_type is CacheNodeType.policy:
        return settings.semantic_cache_policy_ttl_s
    return settings.semantic_cache_classifier_ttl_s


# --------------------------------------------------------------------------- #
# Lookup.                                                                       #
# --------------------------------------------------------------------------- #
def cache_lookup(
    session: Session,
    *,
    key: CacheKey,
    prompt: str,
    content_version: str = "",
) -> dict[str, Any] | None:
    """Return a cached response dict for ``prompt`` within ``key``'s namespace, or None.

    Real embedder -> cosine nearest neighbour at/above the configured threshold; stub
    embedder -> exact normalized-prompt match. Expired rows are pruned and skipped; a
    ``content_version`` mismatch (the grounding rows changed) is a miss. ANY failure is
    swallowed (-> None) so the caller degrades to a live LLM call, never an error.

    PRECONDITION (load-bearing): ``scan_for_injection`` already passed for this turn —
    the cache sits BEHIND the injection scan (ADR-0033), never ahead of it.
    """
    if not settings.semantic_cache_enabled:
        return None
    try:
        norm = normalize_prompt(prompt)
        if _is_stub_embedder():
            entry = _lookup_exact(session, key=key, norm_prompt=norm)
        else:
            entry = _lookup_semantic(session, key=key, prompt=prompt)
        if entry is None:
            return None
        # Content-version invalidation: a policy edit (or any grounding change) busts the
        # entry even before TTL. Empty content_version on both sides = no grounding to bust.
        if entry.content_version != content_version:
            return None
        return dict(entry.response)
    except Exception as exc:  # noqa: BLE001 - cache is best-effort; never surface
        _log.warning("semantic cache lookup failed (degrading to live LLM): %s", exc)
        return None


def _namespace_clause(key: CacheKey) -> list[Any]:
    """SQL predicates pinning a row to ``key``'s namespace (+ not expired)."""
    now = datetime.now(UTC)
    clauses = [
        SemanticCacheEntry.node_type == key.node_type.value,
        SemanticCacheEntry.provider == key.provider,
        SemanticCacheEntry.model == key.model,
        SemanticCacheEntry.embed_provider == key.embed_provider,
        SemanticCacheEntry.embed_dim == key.embed_dim,
        SemanticCacheEntry.expires_at > now,
    ]
    if key.store_id is None:
        clauses.append(SemanticCacheEntry.store_id.is_(None))
    else:
        clauses.append(SemanticCacheEntry.store_id == key.store_id)
    return clauses


def _lookup_exact(
    session: Session, *, key: CacheKey, norm_prompt: str
) -> SemanticCacheEntry | None:
    """Stub-embedder tier: exact normalized-prompt match within the namespace."""
    stmt = (
        select(SemanticCacheEntry)
        .where(*_namespace_clause(key), SemanticCacheEntry.norm_prompt == norm_prompt)
        .order_by(SemanticCacheEntry.created_at.desc())
        .limit(1)
    )
    return session.scalar(stmt)


def _lookup_semantic(
    session: Session, *, key: CacheKey, prompt: str
) -> SemanticCacheEntry | None:
    """Real-embedder tier: nearest cosine neighbour within the namespace, gated by threshold.

    Embeds the prompt via ``embed_query`` (the RETRIEVAL_QUERY task path; ADR-0032 — the
    same space the entry was stored in), runs a cosine ``<=>`` ANN over the HNSW index, and
    accepts the top hit only if its cosine similarity (1 - distance) >= the configured
    threshold (0.95). Below threshold = a topic match, not a paraphrase -> a miss.
    """
    query_vec = get_embedder().embed_query(prompt)
    distance = SemanticCacheEntry.query_embedding.cosine_distance(query_vec)
    stmt = (
        select(SemanticCacheEntry, distance.label("distance"))
        .where(*_namespace_clause(key))
        .order_by(distance.asc())
        .limit(1)
    )
    row = session.execute(stmt).first()
    if row is None:
        return None
    entry: SemanticCacheEntry = row[0]
    similarity = 1.0 - float(row[1])
    if similarity < settings.semantic_cache_threshold:
        return None
    return entry


# --------------------------------------------------------------------------- #
# Store.                                                                        #
# --------------------------------------------------------------------------- #
def cache_store(
    session: Session,
    *,
    key: CacheKey,
    prompt: str,
    response: dict[str, Any],
    source_ids: list[str] | None = None,
    content_version: str = "",
) -> None:
    """Memoize a SUCCESSFUL, allow-listed response under ``key``'s namespace.

    The caller hands only an allow-listed success here — never an ``APIError``, refusal, or
    personalized/tool-derived output (those are the NEVER-cache list, enforced upstream).
    Embeds the prompt (the query side) for the similarity tier, records the grounding
    ``source_ids`` + ``content_version`` for invalidation, and stamps ``expires_at`` from
    the node's TTL. ANY failure is swallowed (a store error is a no-op, never surfaced).
    """
    if not settings.semantic_cache_enabled:
        return
    try:
        norm = normalize_prompt(prompt)
        query_vec = get_embedder().embed_query(prompt)
        expires_at = datetime.now(UTC) + timedelta(seconds=_ttl_for(key.node_type))
        session.add(
            SemanticCacheEntry(
                node_type=key.node_type.value,
                provider=key.provider,
                model=key.model,
                embed_provider=key.embed_provider,
                embed_dim=key.embed_dim,
                store_id=key.store_id,
                norm_prompt=norm,
                query_embedding=query_vec,
                response=response,
                source_ids=source_ids or [],
                content_version=content_version,
                expires_at=expires_at,
            )
        )
        session.flush()
    except Exception as exc:  # noqa: BLE001 - cache is best-effort; never surface
        _log.warning("semantic cache store failed (ignored): %s", exc)


def purge_expired(session: Session) -> int:
    """Delete expired cache rows (TTL sweep). Returns the row count removed."""
    result = session.execute(
        delete(SemanticCacheEntry).where(
            SemanticCacheEntry.expires_at <= datetime.now(UTC)
        )
    )
    session.flush()
    return cast("CursorResult[Any]", result).rowcount or 0


__all__ = [
    "CacheKey",
    "CacheNodeType",
    "cache_lookup",
    "cache_store",
    "normalize_prompt",
    "purge_expired",
    "runtime_cache_key",
]
