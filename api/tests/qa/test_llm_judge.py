"""Free-tier LLM judge — arming + score-parsing layer (US-E7-EJ, ADR-0033 §3 addendum).

LAYER SPLIT — what THIS owns vs what it does NOT re-assert
=========================================================
This is the **judge-specific** layer for the new free-tier ``LlmJudge``. It adds only:

  * that the ``LlmJudge`` is registered under ``"llm"`` and ARMS the gate (non-deterministic
    identity), so the numeric floors GATE under it exactly like the Claude judge;
  * that the deterministic stub SMOKE is intact (still does not arm);
  * that score parsing clamps to ``[0,1]`` and malformed model output degrades safely.

It does NOT re-assert Juno's gate atoms (the floor-defect mechanics, refusal/injection
determinism, the smoke run shape) — those live in ``tests/qa/test_ragas_gate.py``. The
arming GATING-vs-SMOKE proof here uses the real ``LlmJudge`` (with an injected fake chat
model) where the gate test used a hand-rolled ``_FixedJudge`` stand-in.

KEY-FREE: no provider call ever happens. The ``LlmJudge`` is constructed with an injected
fake chat model whose ``with_structured_output(...).invoke(...)`` returns known scores —
the same key-free seam the orchestrator tests use for the runtime brains.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.orm import Session

from app.db.models import User
from app.eval.dataset import GoldenRecord, load_golden
from app.eval.gate import is_armed, run_gate
from app.eval.judge import _JUDGES, LlmJudge, _coerce_score, _ScoreOut, get_judge
from tests.conftest import ResolvedHandles, SeededDb
from tests.fixtures.handles import PERSONAS


# --------------------------------------------------------------------------- #
# Fake chat model — the key-free structured-output seam.                        #
# --------------------------------------------------------------------------- #
class _FakeStructuredRunnable:
    """Stands in for ``model.with_structured_output(_ScoreOut)``; returns a fixed value."""

    def __init__(self, value: object) -> None:
        self._value = value

    def invoke(self, _messages: object, **_kwargs: Any) -> object:
        return self._value


class _FakeChatModel:
    """A minimal chat model exposing only ``with_structured_output`` (no provider, no key).

    ``returns`` is whatever the bound scorer should yield on ``invoke`` — a ``_ScoreOut``,
    a plain dict, or a malformed object, so one fake covers the happy + degraded paths.
    """

    def __init__(self, returns: object) -> None:
        self._returns = returns

    def with_structured_output(self, _schema: object, **_kwargs: Any) -> _FakeStructuredRunnable:
        return _FakeStructuredRunnable(self._returns)


def _llm_judge(returns: object) -> LlmJudge:
    """Build the REAL LlmJudge over a fake chat model — no get_chat_model(), no key.

    The fake duck-types the ONE method ``LlmJudge`` uses (``with_structured_output``); we
    cast to ``BaseChatModel`` so the injection seam stays typed without subclassing the
    full chat-model ABC (the orchestrator tests inject stub BRAINS for the same reason).
    """
    return LlmJudge(model=cast(BaseChatModel, _FakeChatModel(returns)))


def _record() -> GoldenRecord:
    return next(r for r in load_golden() if r.id == "EVAL-018")  # return-window policy item


def _user(session: Session, handles: ResolvedHandles, persona: str) -> User:
    uid = handles.user_ids[PERSONAS[persona].handle]
    user = session.get(User, uid)
    assert user is not None
    return user


# =========================================================================== #
# 1. Registration + arming: the free-tier judge arms like Claude.              #
# =========================================================================== #
def test_llm_judge_registered_under_llm_slot() -> None:
    """The ``"llm"`` slot resolves to LlmJudge; the registry keeps deterministic + claude."""
    assert _JUDGES["llm"] is LlmJudge
    assert {"deterministic", "llm", "claude"} <= set(_JUDGES)


def test_llm_judge_identity_arms_the_gate() -> None:
    """The LlmJudge identity is non-deterministic -> ``is_armed`` is True (arms the floors)."""
    judge = _llm_judge(_ScoreOut(response_relevancy=0.9, faithfulness=0.95))
    assert judge.identity.startswith("llm:")
    assert not judge.identity.startswith("deterministic:")
    assert is_armed(judge)


def test_get_judge_unknown_still_fails_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    """A typo'd EVAL_JUDGE never silently degrades to the stub (existing fail-loud pattern).

    Patches the EXACT ``settings`` binding ``get_judge`` reads — the one in
    ``app.eval.judge`` (it does ``from app.core.config import settings``). This matters:
    the ``seeded_db`` fixture ``importlib.reload``s the config module elsewhere, which
    rebinds ``app.core.config.settings`` to a NEW object while ``app.eval.judge`` keeps the
    old one — so patching the config module's settings would miss. The string target +
    monkeypatch keep the override isolated and auto-restored on teardown.
    """
    monkeypatch.setattr("app.eval.judge.settings.eval_judge", "groqq")  # typo
    with pytest.raises(ValueError, match="Unknown EVAL_JUDGE"):
        get_judge()


# =========================================================================== #
# 2. Score parsing: clamp to [0,1], malformed output degrades safely.          #
# =========================================================================== #
def test_score_parses_structured_output() -> None:
    """The happy path: a ``_ScoreOut`` is returned as-is (already in range)."""
    judge = _llm_judge(_ScoreOut(response_relevancy=0.84, faithfulness=0.91))
    scores = judge.score(_record(), answer="The return window is 30 days.", contexts=["..."])
    assert scores.response_relevancy == pytest.approx(0.84)
    assert scores.faithfulness == pytest.approx(0.91)


def test_score_clamps_out_of_range_values() -> None:
    """Out-of-[0,1] model output is clamped, not trusted (a 1.4 must not pass as >floor)."""
    judge = _llm_judge(_ScoreOut(response_relevancy=1.4, faithfulness=-0.3))
    scores = judge.score(_record(), answer="x", contexts=[])
    assert scores.response_relevancy == 1.0
    assert scores.faithfulness == 0.0


def test_score_accepts_dict_structured_output() -> None:
    """Some providers' structured-output mode returns a dict — handled, then clamped."""
    judge = _llm_judge({"response_relevancy": 0.7, "faithfulness": 0.6})
    scores = judge.score(_record(), answer="x", contexts=[])
    assert scores.response_relevancy == pytest.approx(0.7)
    assert scores.faithfulness == pytest.approx(0.6)


def test_malformed_output_degrades_to_zero_not_crash() -> None:
    """A missing/non-numeric field degrades to 0.0 (worst score) — documented, not a crash."""
    # Missing both fields entirely.
    assert _coerce_score({}, "faithfulness") == 0.0
    # Non-numeric value.
    assert _coerce_score({"faithfulness": "high"}, "faithfulness") == 0.0
    # An object with neither attribute nor key.
    assert _coerce_score(object(), "response_relevancy") == 0.0
    # End-to-end through the judge: a junk return degrades both scores to 0.0, no exception.
    judge = _llm_judge({"unexpected": 1})
    scores = judge.score(_record(), answer="x", contexts=[])
    assert scores.response_relevancy == 0.0
    assert scores.faithfulness == 0.0


# =========================================================================== #
# 3. Arming end-to-end: floors GATE under LlmJudge, SMOKE intact under stub.    #
# =========================================================================== #
def test_llm_judge_floors_GATE_when_armed_and_below(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """ARMED via the real LlmJudge + below-floor scores -> floor defects recorded (gates).

    Proves the new judge ARMS the §3 floors through the actual gate, not just by identity:
    a below-floor faithfulness/relevancy becomes a tracked ``floor:*`` defect and the gate
    does NOT pass. Key-free — the LlmJudge runs over an injected fake chat model.
    """
    judge = _llm_judge(_ScoreOut(response_relevancy=0.10, faithfulness=0.20))
    assert is_armed(judge)
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        report = run_gate(s, user, judge=judge)
        s.commit()
    assert report.armed is True
    kinds = {d.kind for d in report.defects}
    assert "floor:faithfulness" in kinds
    assert "floor:answer_relevancy" in kinds
    assert not report.passed


def test_llm_judge_floors_GATE_when_armed_and_clear(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """ARMED via the real LlmJudge + above-floor scores -> no floor defects."""
    judge = _llm_judge(_ScoreOut(response_relevancy=0.95, faithfulness=0.97))
    assert is_armed(judge)
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        report = run_gate(s, user, judge=judge)
        s.commit()
    assert report.armed is True
    assert [d for d in report.defects if d.kind.startswith("floor:")] == []


def test_deterministic_smoke_still_does_not_arm(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """The DeterministicJudge SMOKE is intact: no floor defects even with below-floor scores.

    The complement to the LlmJudge arming proof — adding the free-tier judge must NOT change
    the key-free smoke path. Under the default deterministic stub the gate never records a
    ``floor:*`` defect, so CI (no key) still passes.
    """
    from app.eval.judge import DeterministicJudge

    judge = DeterministicJudge()
    assert not is_armed(judge)
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        report = run_gate(s, user, judge=judge)
        s.commit()
    assert report.armed is False
    assert [d for d in report.defects if d.kind.startswith("floor:")] == []
