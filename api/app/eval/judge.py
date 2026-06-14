"""Judge seam — the LLM-judge metrics (response relevancy + faithfulness) (US-E7-00).

These two RAGAS metrics are semantic and, in a real run, need an LLM judge. To keep the
default path CI-safe (no keys, no network) they sit behind a ``Judge`` Protocol:

* ``Judge`` — the Protocol: score ``response_relevancy`` and ``faithfulness`` in
  ``[0, 1]`` for one sample (question / answer / contexts / ground_truth).
* ``DeterministicJudge`` — the DEFAULT. Derives reproducible scores from lexical /
  source-overlap heuristics (:mod:`app.eval.metrics`):
    - response relevancy ≈ token overlap of the answer with the question + ground truth
      (does the answer address what was asked, the way the reference does);
    - faithfulness ≈ how much of the answer is contained in the retrieved contexts +
      ground truth (penalises claims not grounded in context).
  This is a **harness-exercising stub, not a semantic judge** — its numbers prove the
  pipeline runs and are well-formed, NOT that an answer is good. The §4 quality gates in
  ``qa-matrix.md`` only become meaningful under a REAL judge.
* ``get_judge()`` — resolves ``settings.eval_judge`` (default ``"deterministic"``). A
  real Claude judge registers in ``_JUDGES`` and is selected by flipping ``EVAL_JUDGE``;
  unknown judges fail loudly (like ``get_embedder``).

CLAUDE-AS-JUDGE WHEN KEYS LAND
==============================
Per CLAUDE.md, the eval JUDGE is separate from the runtime PRODUCT LLM (which stays
Groq/Gemini free-tier). When a judge key lands, a ``ClaudeJudge`` registers under
``"claude"`` and defaults to the latest Claude model — :data:`DEFAULT_JUDGE_MODEL`
(``claude-opus-4-8``). That id appears ONLY as the registered default for the
not-yet-active Claude provider; nothing in the default path imports or calls it. A real
``ragas`` integration would also slot in here (wrap RAGAS's metrics behind this same
Protocol) — see the ADR for why we do NOT take a hard ``ragas`` dependency.
"""

from __future__ import annotations

from typing import NamedTuple, Protocol

from app.core.config import settings
from app.eval.dataset import GoldenRecord
from app.eval.metrics import clamp01, containment, jaccard

# The latest Claude model the real eval judge defaults to once a key lands. Referenced
# only as a registered default for the (inert) Claude provider — never called here.
DEFAULT_JUDGE_MODEL = "claude-opus-4-8"


class JudgeScores(NamedTuple):
    """The two LLM-judge metric scores for one sample, each in ``[0, 1]``."""

    response_relevancy: float
    faithfulness: float


class Judge(Protocol):
    """A pluggable judge for the LLM-judge RAGAS metrics.

    ``identity`` is a stable tag written into the score artifact so a deterministic run
    is always distinguishable from a real-judge run.
    """

    @property
    def identity(self) -> str: ...

    def score(
        self, record: GoldenRecord, *, answer: str, contexts: list[str]
    ) -> JudgeScores: ...


class DeterministicJudge:
    """Default CI-safe judge — reproducible lexical heuristics, NOT a semantic judge.

    response relevancy: how well the answer's tokens overlap the question AND the
    reference answer (addresses-the-ask proxy). faithfulness: how much of the answer is
    contained in the retrieved contexts + ground truth (grounded-claims proxy). Both are
    bounded to ``[0, 1]``; identical inputs always yield identical scores.
    """

    identity = "deterministic:lexical-overlap-v0"

    def score(
        self, record: GoldenRecord, *, answer: str, contexts: list[str]
    ) -> JudgeScores:
        # Relevancy: does the answer address the question, the way the reference does?
        # Average the answer's overlap with the question and with the ground truth so a
        # refusal answer (low question overlap, high ground-truth overlap) still scores
        # sensibly without being penalised for not echoing the question verbatim.
        rel_to_question = jaccard(answer, record.question)
        rel_to_truth = jaccard(answer, record.expected_answer)
        relevancy = clamp01((rel_to_question + rel_to_truth) / 2.0)

        # Faithfulness: is the answer grounded? Score how much of the answer is contained
        # in (retrieved contexts ∪ ground truth). With keyword-only retrieval contexts
        # may be sparse, so the ground truth backstops the grounding source — the stub
        # judge measures "supported by what we have", not semantic entailment.
        grounding = "\n".join([*contexts, record.expected_answer])
        faithfulness = clamp01(containment(answer, grounding))

        return JudgeScores(response_relevancy=relevancy, faithfulness=faithfulness)


_JUDGES: dict[str, type[Judge]] = {
    "deterministic": DeterministicJudge,
}


def get_judge() -> Judge:
    """Resolve the active judge from ``settings.eval_judge`` (default ``deterministic``).

    Unknown judges fail loudly so a typo in ``EVAL_JUDGE`` never silently degrades the
    eval to the stub. A real ``ClaudeJudge`` registers in ``_JUDGES`` under ``"claude"``.
    """
    name = settings.eval_judge
    try:
        judge_cls = _JUDGES[name]
    except KeyError:
        raise ValueError(
            f"Unknown EVAL_JUDGE {name!r}. Registered: {sorted(_JUDGES)}. "
            "A real Claude judge registers in app/eval/judge.py::_JUDGES "
            f"(default model {DEFAULT_JUDGE_MODEL!r})."
        ) from None
    return judge_cls()
