"""Deterministic eval metric math — shared, no-LLM, no-DB (US-E7-00).

Two families live here, both pure-Python over the stdlib:

* **set-overlap retrieval metrics** — context precision / recall computed from a
  question's retrieved contexts vs its gold ``source_docs``. This is the SAME formula
  the retrieval smoke uses (``test_retrieval_smoke.py``); it is factored here so the
  smoke and the RAGAS harness share one definition and can't silently drift.
* **lexical-overlap helpers** — a tokeniser + Jaccard/containment used by the
  :class:`~app.eval.judge.DeterministicJudge` to derive reproducible (but NOT semantic)
  relevancy/faithfulness scores. Kept here so all the deterministic math is unit-pinned
  in one place.

Every score is a float in ``[0, 1]``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# ----------------------------------------------------------------- retrieval metrics


def context_recall(relevant: set[str], retrieved: Iterable[str]) -> float:
    """recall = |relevant ∩ retrieved| / |relevant|.

    Of a question's gold contexts, how many were retrieved. Empty ``relevant`` -> 1.0
    (nothing was required, so nothing was missed) — the harness skips no-gold items
    upstream, but the math stays total.
    """
    rel = set(relevant)
    if not rel:
        return 1.0
    hits = rel & set(retrieved)
    return len(hits) / len(rel)


def context_precision(relevant: set[str], retrieved: list[str], *, k: int | None = None) -> float:
    """precision = |relevant ∩ topk| / min(k, n_retrieved).

    Of the (top-k) retrieved contexts, how many are gold. ``k=None`` scores the full
    retrieved list. Empty retrieval -> 0.0 (nothing on-topic was returned). This is the
    retrieval smoke's exact precision@k definition.
    """
    topk = retrieved[:k] if k is not None else list(retrieved)
    if not topk:
        return 0.0
    denom = min(k, len(topk)) if k is not None else len(topk)
    hits = set(relevant) & set(topk)
    return len(hits) / denom


# ----------------------------------------------------------------- lexical overlap

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Tiny English stoplist so trivial function words don't dominate overlap. Deliberately
# small + frozen — this is a harness heuristic, not an NLP component.
_STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do", "does",
        "for", "from", "how", "i", "if", "in", "is", "it", "its", "me", "my", "no",
        "not", "of", "on", "or", "the", "to", "what", "when", "you", "your", "with",
        "we", "this", "that", "they", "them",
    }
)


def tokenize(text: str) -> set[str]:
    """Lowercase word-token set with stopwords removed (deterministic)."""
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS}


def jaccard(a: str, b: str) -> float:
    """Jaccard similarity of two texts' token sets. Both empty -> 1.0."""
    ta, tb = tokenize(a), tokenize(b)
    if not ta and not tb:
        return 1.0
    union = ta | tb
    if not union:
        return 0.0
    return len(ta & tb) / len(union)


def containment(claim: str, source: str) -> float:
    """Fraction of ``claim``'s tokens that appear in ``source`` (asymmetric).

    Used as a crude faithfulness proxy: how much of the answer is "grounded" in the
    retrieved context. Empty claim -> 1.0 (nothing unsupported was asserted).
    """
    tc = tokenize(claim)
    if not tc:
        return 1.0
    ts = tokenize(source)
    return len(tc & ts) / len(tc)


def clamp01(value: float) -> float:
    """Clamp a score into ``[0, 1]`` (defends against float drift)."""
    return max(0.0, min(1.0, value))
