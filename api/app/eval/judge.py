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
* ``LlmJudge`` — the RECOMMENDED armed judge. Scores via the SAME free-tier provider as
  the product runtime (Groq/Gemini, through :func:`app.agent.llm.get_chat_model` /
  ``LLM_PROVIDER``), so ONE free-tier key arms both the app and the eval gate — no paid
  Anthropic key needed. Registered under ``"llm"``.
* ``ClaudeJudge`` — an OPTIONAL paid judge (separate Anthropic key). Kept registered.
* ``get_judge()`` — resolves ``settings.eval_judge`` (default ``"deterministic"``). The
  ``LlmJudge``/``ClaudeJudge`` register in ``_JUDGES`` and are selected by flipping
  ``EVAL_JUDGE``; unknown judges fail loudly (like ``get_embedder``).

FREE-TIER LLM JUDGE (recommended) vs CLAUDE (optional)
======================================================
The eval JUDGE is separate from the runtime PRODUCT LLM only in *role*, not in *provider*:
the recommended ``LlmJudge`` reuses the runtime chat model (``get_chat_model()``), so the
same Groq/Gemini free-tier key that runs the product also arms the gate. The ``ClaudeJudge``
stays available for anyone who wants a paid Anthropic judge; :data:`DEFAULT_JUDGE_MODEL`
(``claude-opus-4-8``) is only its registered default. Both judges have a non-deterministic
``identity`` so :func:`app.eval.gate.is_armed` arms the numeric floors under either — the
``DeterministicJudge`` (identity prefixed ``deterministic:``) is the only smoke. Module
import stays key-free: every live judge imports its SDK / builds its client lazily.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple, Protocol

from pydantic import BaseModel, Field

from app.core.config import settings
from app.eval.dataset import GoldenRecord
from app.eval.metrics import clamp01, containment, jaccard

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

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


class ClaudeJudge:
    """The REAL LLM judge — Claude scores relevancy + faithfulness (US-QA-D16, ADR-0033).

    This is the live judge that ARMS the RAGAS v1 numeric floors (faithfulness ≥ 0.90,
    relevancy ≥ 0.80). It is the human's LOCAL-ONLY concern: the eval judge is SEPARATE
    from the runtime product LLM (Groq/Gemini free-tier) and uses a paid Anthropic key
    that lives only in the gitignored ``.env``. CI has no key, so this judge is
    REGISTERED-BUT-NOT-CONSTRUCTED there — importing this module must never require the
    key (the ``anthropic`` client is imported lazily, inside ``score``/``__init__``).

    Arming contract (ADR-0033 §3): ``run_gate`` only constructs this judge when
    ``EVAL_JUDGE=claude`` AND a key is present; absent either, the gate falls back to the
    :class:`DeterministicJudge` as a CI-safe smoke and the floors do NOT hard-fail. So
    nothing on the default/CI path ever imports ``anthropic`` or calls Anthropic.
    """

    def __init__(self, *, model: str | None = None, api_key: str | None = None) -> None:
        # Lazy import: the anthropic SDK is an optional, local-only dependency. Importing
        # app.eval.judge (CI default path) must not require it.
        from anthropic import Anthropic  # type: ignore[import-not-found]  # noqa: PLC0415

        self._model = model or settings.eval_judge_model
        key = api_key or settings.anthropic_api_key
        if not key:
            raise ValueError(
                "ClaudeJudge needs an Anthropic key (settings.anthropic_api_key / "
                "ANTHROPIC_API_KEY). It is local-only; CI runs the DeterministicJudge."
            )
        self._client = Anthropic(api_key=key)

    @property
    def identity(self) -> str:
        return f"claude:{self._model}"

    def score(
        self, record: GoldenRecord, *, answer: str, contexts: list[str]
    ) -> JudgeScores:  # pragma: no cover - live Anthropic call, local-only (no key in CI)
        import json  # noqa: PLC0415

        grounding = "\n\n".join(contexts) if contexts else "(no retrieved context)"
        prompt = (
            "You are a strict RAGAS judge. Score one answer on two metrics, each a float "
            "in [0,1]. Return ONLY JSON: "
            '{"response_relevancy": <float>, "faithfulness": <float>}.\n\n'
            "- response_relevancy: does the ANSWER address the QUESTION the way the "
            "REFERENCE answer does? (a correct refusal of an out-of-scope question is "
            "highly relevant).\n"
            "- faithfulness: is every claim in the ANSWER grounded in the retrieved "
            "CONTEXT (or, for a refusal, justified by the absence of support)? Penalise "
            "any claim not supported by the context.\n\n"
            f"QUESTION:\n{record.question}\n\n"
            f"REFERENCE ANSWER:\n{record.expected_answer}\n\n"
            f"RETRIEVED CONTEXT:\n{grounding}\n\n"
            f"ANSWER TO SCORE:\n{answer}\n"
        )
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in msg.content if getattr(block, "type", "") == "text"
        )
        data = json.loads(text[text.index("{") : text.rindex("}") + 1])
        return JudgeScores(
            response_relevancy=clamp01(float(data["response_relevancy"])),
            faithfulness=clamp01(float(data["faithfulness"])),
        )


class _ScoreOut(BaseModel):
    """Structured-output schema the LLM judge returns (numeric, bounded by prompt + clamp).

    Mirrors the orchestrator's ``with_structured_output`` pattern: the model emits this
    typed object directly, so we never parse free-text. Both fields are scored in [0,1];
    we still clamp defensively in :meth:`LlmJudge.score` (a model may drift out of range).
    """

    response_relevancy: float = Field(
        description="Does the ANSWER address the QUESTION the way the REFERENCE does? [0,1]"
    )
    faithfulness: float = Field(
        description="Is every claim in the ANSWER grounded in the retrieved CONTEXT? [0,1]"
    )


_LLM_JUDGE_SYSTEM = (
    "You are a strict RAGAS judge. Score ONE answer on two metrics, each a float in [0,1].\n"
    "- response_relevancy: does the ANSWER address the QUESTION the way the REFERENCE "
    "answer does? A correct refusal of an out-of-scope question is HIGHLY relevant.\n"
    "- faithfulness: is every claim in the ANSWER grounded in the retrieved CONTEXT (or, "
    "for a refusal, justified by the absence of support)? Penalise any claim not supported "
    "by the context. Be calibrated and deterministic; do not reward verbosity."
)


class LlmJudge:
    """RECOMMENDED armed judge — scores via the free-tier runtime provider (US-E7-EJ).

    Calls the SAME chat model the product's agents use (:func:`app.agent.llm.get_chat_model`,
    selected by ``LLM_PROVIDER`` = Groq|Gemini), with ``with_structured_output`` so the
    model returns numeric scores directly (mirrors the orchestrator's classify node). One
    free-tier key therefore arms BOTH the runtime and the eval gate — NO paid Anthropic key.

    Key-free import contract (mirrors :class:`ClaudeJudge`): the chat model is built lazily
    on construction via ``get_chat_model()``, which raises if no provider key is set. So
    importing this module never needs a key, and CI (no key, ``EVAL_JUDGE=deterministic``)
    never constructs this judge. Tests inject a fake ``model`` to exercise scoring key-free.

    The non-deterministic ``identity`` (``llm:<provider>:<model>``) arms the gate's numeric
    floors via :func:`app.eval.gate.is_armed`, exactly like the Claude judge.
    """

    def __init__(self, *, model: BaseChatModel | None = None) -> None:
        # ``resolved`` is the chat model to score with: an injected fake (tests) or the
        # runtime provider with failover (``get_chat_model`` returns a ``FailoverChatModel``,
        # which proxies ``with_structured_output`` across both providers). Typed ``Any`` so
        # the failover wrapper (not a ``BaseChatModel`` subclass) is accepted here.
        resolved: Any = model
        if resolved is None:
            # Lazy: get_chat_model() builds the Groq/Gemini client and raises with a clear
            # message if the provider key is absent (so import stays key-free; CI never
            # reaches here under the deterministic default).
            from app.agent.llm import get_chat_model  # noqa: PLC0415

            resolved = get_chat_model()
        # Low temperature is already set by the provider factory (temperature=0.0) for a
        # deterministic-leaning score; structured output binds the typed schema.
        self._provider = settings.llm_provider
        self._model_name = settings.eval_llm_model or _runtime_model_name()
        self._scorer = resolved.with_structured_output(_ScoreOut)

    @property
    def identity(self) -> str:
        return f"llm:{self._provider}:{self._model_name}"

    def score(
        self, record: GoldenRecord, *, answer: str, contexts: list[str]
    ) -> JudgeScores:
        from langchain_core.messages import HumanMessage, SystemMessage  # noqa: PLC0415

        grounding = "\n\n".join(contexts) if contexts else "(no retrieved context)"
        user = (
            f"QUESTION:\n{record.question}\n\n"
            f"REFERENCE ANSWER:\n{record.expected_answer}\n\n"
            f"RETRIEVED CONTEXT:\n{grounding}\n\n"
            f"ANSWER TO SCORE:\n{answer}\n"
        )
        result = self._scorer.invoke(
            [SystemMessage(content=_LLM_JUDGE_SYSTEM), HumanMessage(content=user)]
        )
        # Defensive: structured output SHOULD yield _ScoreOut, but a provider may return a
        # dict (or drift the fields). Degrade safely to 0.0 rather than crash the gate, and
        # clamp to [0,1] — a malformed score must never silently pass a semantic floor.
        rel = _coerce_score(result, "response_relevancy")
        faith = _coerce_score(result, "faithfulness")
        return JudgeScores(response_relevancy=rel, faithfulness=faith)


def _runtime_model_name() -> str:
    """The runtime provider's configured model name (for the judge identity tag)."""
    if settings.llm_provider == "gemini":
        return settings.gemini_model
    return settings.groq_model


def _coerce_score(result: object, field: str) -> float:
    """Pull one score from the structured output, clamped to [0,1]; 0.0 on anything off.

    Accepts the ``_ScoreOut`` Pydantic object (the happy path) or a plain ``dict`` (some
    providers' structured-output mode returns one). A missing field or a non-numeric /
    NaN value degrades to 0.0 — documented behaviour: a malformed judge response is treated
    as the worst score, never a crash and never a silent pass of a semantic floor.
    """
    if isinstance(result, _ScoreOut):
        value: object = getattr(result, field)
    elif isinstance(result, dict):
        value = result.get(field)
    else:
        value = getattr(result, field, None)
    try:
        score = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if score != score:  # NaN guard (NaN != NaN)
        return 0.0
    return clamp01(score)


_JUDGES: dict[str, type[Judge]] = {
    "deterministic": DeterministicJudge,
    "llm": LlmJudge,
    "claude": ClaudeJudge,
}


def get_judge() -> Judge:
    """Resolve the active judge from ``settings.eval_judge`` (default ``deterministic``).

    Registered slots: ``"deterministic"`` (CI smoke), ``"llm"`` (RECOMMENDED armed judge —
    the free-tier runtime provider via ``get_chat_model()``/``LLM_PROVIDER``), ``"claude"``
    (optional paid Anthropic judge). Unknown judges fail loudly so a typo in ``EVAL_JUDGE``
    never silently degrades the eval to the stub. Live judges construct their client only
    when a key is present (lazy), so this resolver stays key-free to import.
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
