"""RAGAS harness — score one golden record on all four metrics (US-E7-00).

This is the layer ABOVE the retrieval smoke: the smoke computes the retrieval half
(context precision/recall) against the live keyword search; this harness adds the
**judge half** (response relevancy + faithfulness) via the pluggable answerer + judge
seams, and assembles a typed per-item result.

The harness is deliberately **DB-agnostic**: it takes the already-retrieved contexts
for a record as input (the runner gets them from the live ``GET /search`` for
product-grounded items, the same way the smoke does). That keeps the scoring logic
pure and unit-testable, and lets a future semantic/policy retriever feed the SAME
harness without change.

Each result carries the four scores, the gold/retrieved context keys, the (stub) answer
+ whether it refused, and the answerer/judge identities so a deterministic run is always
distinguishable from a real one.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.eval.answerer import Answerer, looks_like_refusal
from app.eval.dataset import GoldenRecord
from app.eval.judge import Judge
from app.eval.metrics import context_precision, context_recall


class ItemScores(BaseModel):
    """The four RAGAS metric scores for one item, each in ``[0, 1]``."""

    model_config = ConfigDict(frozen=True)

    context_precision: float = Field(ge=0.0, le=1.0)
    context_recall: float = Field(ge=0.0, le=1.0)
    response_relevancy: float = Field(ge=0.0, le=1.0)
    faithfulness: float = Field(ge=0.0, le=1.0)


class ItemResult(BaseModel):
    """A scored golden item — scores + the evidence behind them."""

    model_config = ConfigDict(frozen=True)

    id: str
    question: str
    tags: dict[str, object]
    gold_context_keys: list[str]
    retrieved_context_keys: list[str]
    answer: str
    expects_refusal: bool
    answer_refused: bool
    scores: ItemScores


def score_record(
    record: GoldenRecord,
    *,
    gold_context_keys: set[str],
    retrieved_context_keys: list[str],
    retrieved_context_texts: list[str],
    answerer: Answerer,
    judge: Judge,
    k: int | None = None,
) -> ItemResult:
    """Score one golden record on all four metrics.

    ``gold_context_keys`` / ``retrieved_context_keys`` are the resolved context KEYS
    (product slug / policy ``kind@store``) for the deterministic precision/recall math.
    ``retrieved_context_texts`` are the corresponding context bodies the judge reads for
    faithfulness. The answerer produces the answer the judge metrics score.
    """
    precision = context_precision(gold_context_keys, retrieved_context_keys, k=k)
    recall = context_recall(gold_context_keys, retrieved_context_keys)

    answer = answerer.answer(record, retrieved_context_texts)
    judged = judge.score(record, answer=answer, contexts=retrieved_context_texts)

    return ItemResult(
        id=record.id,
        question=record.question,
        tags=record.tags.model_dump(),
        gold_context_keys=sorted(gold_context_keys),
        retrieved_context_keys=retrieved_context_keys,
        answer=answer,
        expects_refusal=record.tags.expects_refusal,
        answer_refused=looks_like_refusal(answer),
        scores=ItemScores(
            context_precision=precision,
            context_recall=recall,
            response_relevancy=judged.response_relevancy,
            faithfulness=judged.faithfulness,
        ),
    )


def mean(values: list[float]) -> float:
    """Arithmetic mean, 0.0 over an empty list (no items scored)."""
    return sum(values) / len(values) if values else 0.0


class HarnessSummary(BaseModel):
    """Aggregate of a harness run — the means + scope/refusal bookkeeping."""

    model_config = ConfigDict(frozen=True)

    mean_context_precision: float
    mean_context_recall: float
    mean_response_relevancy: float
    mean_faithfulness: float
    items_scored: int


def summarize(results: list[ItemResult]) -> HarnessSummary:
    """Aggregate per-item results into the four metric means."""
    return HarnessSummary(
        mean_context_precision=mean([r.scores.context_precision for r in results]),
        mean_context_recall=mean([r.scores.context_recall for r in results]),
        mean_response_relevancy=mean([r.scores.response_relevancy for r in results]),
        mean_faithfulness=mean([r.scores.faithfulness for r in results]),
        items_scored=len(results),
    )
