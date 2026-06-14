"""Answerer seam — produces an ``answer`` per golden question (US-E7-00).

The judge metrics (response relevancy, faithfulness) need an ``answer`` to score. No
live agent runtime / SSE loop exists yet (that is later Echo work), so the default is a
CI-safe **stub** behind the same provider-seam shape as ``get_embedder`` /
``get_retriever``:

* ``Answerer`` — the Protocol every implementation satisfies.
* ``StubAnswerer`` — the default. Derives a well-formed, reproducible answer from the
  record's own ``expected_answer`` + retrieved contexts. It is HONEST about being a stub
  (``identity = "stub:expected-answer"``) — it is NOT a model output, only a fixture so
  the pipeline runs end-to-end. For ``expects_refusal`` items it emits a refusal-shaped
  answer so the harness's refusal-awareness signal is exercised.
* ``get_answerer()`` — resolves ``settings.eval_answerer`` (default ``"stub"``). The real
  agent answerer registers in ``_ANSWERERS`` and is selected by flipping ``EVAL_ANSWERER``
  — a one-line swap, no call-site change.

Why derive from ``expected_answer`` and not retrieval alone: with a stub embedder and
keyword-only retrieval, a retrieval-grounded answer would be near-empty for most golden
questions (raw-question keyword recall is ~0 by construction — the captured smoke
finding). Deriving from the labelled answer keeps the deterministic judge metrics
well-formed and reproducible WITHOUT pretending the stub is a real agent.
"""

from __future__ import annotations

from typing import Protocol

from app.core.config import settings
from app.eval.dataset import GoldenRecord

# Phrases that mark a refusal-shaped answer (the stub emits one for expects_refusal
# items; the harness scans answers for these to log refusal behaviour).
REFUSAL_MARKERS: tuple[str, ...] = (
    "no —",
    "no,",
    "we don't",
    "we do not",
    "doesn't carry",
    "does not carry",
    "can't",
    "cannot",
    "unfortunately",
    "not available",
    "not in the catalog",
    "won't claim",
    "won't invent",
)


def looks_like_refusal(answer: str) -> bool:
    """Heuristic: does this answer decline / disclaim rather than assert a fact?"""
    low = answer.lower()
    return any(marker in low for marker in REFUSAL_MARKERS)


class Answerer(Protocol):
    """A pluggable answer source. The real agent answerer satisfies this shape.

    ``identity`` is a stable tag written into the score artifact so a deterministic-stub
    run is always distinguishable from a real-agent run.
    """

    @property
    def identity(self) -> str: ...

    def answer(self, record: GoldenRecord, contexts: list[str]) -> str: ...


class StubAnswerer:
    """Default CI-safe answerer — derives a reproducible answer from the gold record.

    NOT a model output. For non-refusal items it returns the labelled
    ``expected_answer`` verbatim (a faithful, on-topic stand-in so the judge metrics are
    well-formed). For ``expects_refusal`` items it ALSO returns the expected_answer
    (which is itself authored as a grounded refusal in the golden set) — so the refusal
    markers fire and the refusal-awareness signal is exercised honestly.
    """

    identity = "stub:expected-answer"

    def answer(self, record: GoldenRecord, contexts: list[str]) -> str:
        _ = contexts  # retrieval-grounding hook for the real answerer; unused by the stub
        return record.expected_answer


_ANSWERERS: dict[str, type[Answerer]] = {
    "stub": StubAnswerer,
}


def get_answerer() -> Answerer:
    """Resolve the active answerer from ``settings.eval_answerer`` (default ``stub``).

    Unknown answerers fail loudly (like ``get_embedder``) so a typo never silently
    degrades the eval to the stub.
    """
    name = settings.eval_answerer
    try:
        answerer_cls = _ANSWERERS[name]
    except KeyError:
        raise ValueError(
            f"Unknown EVAL_ANSWERER {name!r}. Registered: {sorted(_ANSWERERS)}. "
            "The real agent answerer registers in app/eval/answerer.py::_ANSWERERS."
        ) from None
    return answerer_cls()
