"""RAGAS harness — CI-safe sample run + metric/registry unit pins (US-E7-00).

WHAT THIS IS (and is NOT)
=========================
The judge-half companion to the no-LLM retrieval smoke (``test_retrieval_smoke.py``).
The smoke covers context precision/recall against live keyword search; this exercises
the FULL harness — all four RAGAS metrics — on the **deterministic judge + stub
answerer**, so it runs with NO LLM keys and NO network.

SAMPLE RUN, NOT A QUALITY GATE
==============================
Like the smoke, this asserts the harness RAN and is WELL-FORMED — every mean is a float
in ``[0, 1]``, the artifact is written, the pipeline covered the real in-scope subset,
and refusal awareness is recorded. It does NOT assert quality thresholds on the stub
scores: the deterministic judge is a harness-exercising lexical stub, not a semantic
judge, so a threshold on its numbers would be meaningless (and the §4 qa-matrix gates
only bind under a real judge). The DB-backed run skips cleanly with no DATABASE_URL; the
pure unit tests below always run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.eval.answerer import StubAnswerer, get_answerer, looks_like_refusal
from app.eval.dataset import GoldenRecord, load_golden
from app.eval.harness import score_record
from app.eval.judge import (
    DEFAULT_JUDGE_MODEL,
    DeterministicJudge,
    JudgeScores,
    get_judge,
)
from app.eval.metrics import (
    clamp01,
    containment,
    context_precision,
    context_recall,
    jaccard,
)
from app.eval.runner import run_eval, write_artifact
from tests.conftest import SeededDb

# --------------------------------------------------------------------------- #
# CI-safe DB-backed sample run (deterministic judge + stub answerer).         #
# --------------------------------------------------------------------------- #


def test_ragas_sample_run_is_well_formed(seeded_db: SeededDb, tmp_path: Path) -> None:
    """Run the full harness on the golden set; assert it RAN + is well-formed.

    Deterministic judge + stub answerer (the CI-safe default path). Asserts: the run
    covered the whole golden set, all four means are floats in [0,1], the artifact was
    written with the four means + judge/answerer identity + refusal log, and the
    refusal-awareness signal was recorded for the expected-refusal items. NOT a quality
    gate on the stub scores (see module docstring).
    """
    answerer = get_answerer()
    judge = get_judge()
    assert answerer.identity == "stub:expected-answer"
    assert judge.identity == "deterministic:lexical-overlap-v0"

    with Session(seeded_db.engine) as session:
        results, summary, scope = run_eval(session, answerer=answerer, judge=judge)

    # The run covered the whole golden set (every record scored).
    golden = load_golden()
    assert scope["golden_total"] == len(golden) == 25
    assert summary.items_scored == len(results) == len(golden)
    assert int(scope["product_grounded"]) >= 1  # type: ignore[call-overload]
    assert int(scope["policy_only_no_live_retrieval"]) >= 1  # type: ignore[call-overload]

    # All four means are well-formed floats in [0, 1].
    for value in (
        summary.mean_context_precision,
        summary.mean_context_recall,
        summary.mean_response_relevancy,
        summary.mean_faithfulness,
    ):
        assert isinstance(value, float) and 0.0 <= value <= 1.0

    # Every per-item score is also well-formed.
    for r in results:
        s = r.scores
        for v in (s.context_precision, s.context_recall, s.response_relevancy, s.faithfulness):
            assert 0.0 <= v <= 1.0

    # Refusal awareness: the 4 expects_refusal golden items are flagged, and the stub
    # answerer (which returns the grounded-refusal expected_answer) is detected refusing.
    refusal_items = [r for r in results if r.expects_refusal]
    assert len(refusal_items) == 4
    assert all(r.answer_refused for r in refusal_items)

    # Artifact is written (to a tmp dir so the test never churns the tracked results dir).
    out = write_artifact(
        results, summary, scope, answerer=answerer, judge=judge, results_dir=tmp_path
    )
    assert out.is_file()
    artifact = json.loads(out.read_text(encoding="utf-8"))
    assert artifact["judge"] == "deterministic:lexical-overlap-v0"
    assert artifact["answerer"] == "stub:expected-answer"
    assert set(artifact["means"]) == {
        "mean_context_precision",
        "mean_context_recall",
        "mean_response_relevancy",
        "mean_faithfulness",
        "items_scored",
    }
    assert len(artifact["items"]) == len(golden)
    # Refusal log carries every expects_refusal item.
    logged = {e["id"] for e in artifact["refusal_log"] if e["expects_refusal"]}
    assert logged == {r.id for r in refusal_items}
    # Stable latest pointer also written.
    assert (out.parent / "ragas-latest.json").is_file()


# --------------------------------------------------------------------------- #
# Pure unit tests — metric math + judge/answerer registry (no DB, always run).#
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("k", [1, 5, None])
def test_context_metrics_math(k: int | None) -> None:
    """Pin precision/recall against the smoke's definitions (no DB)."""
    relevant = {"a", "b"}
    retrieved = ["a", "x", "y", "z", "b"]
    recall = context_recall(relevant, retrieved)
    precision = context_precision(relevant, retrieved, k=k)
    assert recall == 1.0  # both relevant present in the full list
    if k == 1:
        assert precision == 1.0  # top-1 is 'a', all 1/1 retrieved are relevant
    elif k == 5:
        assert precision == pytest.approx(2 / 5)  # 2 of top-5 relevant
    else:  # k is None -> full list (len 5)
        assert precision == pytest.approx(2 / 5)


def test_context_metrics_edge_cases() -> None:
    """Empty relevant -> recall 1.0; empty retrieved -> precision 0.0."""
    assert context_recall(set(), ["a"]) == 1.0
    assert context_precision({"a"}, [], k=5) == 0.0
    assert context_recall({"a", "b"}, ["a"]) == 0.5


def test_lexical_helpers() -> None:
    """Jaccard / containment / clamp behave as the deterministic judge expects."""
    assert jaccard("walnut cutting board", "walnut cutting board") == 1.0
    assert jaccard("", "") == 1.0
    # containment: every meaningful claim token is present in the source -> 1.0.
    assert containment("walnut board", "the walnut board is reversible") == 1.0
    assert containment("", "anything") == 1.0
    assert clamp01(1.5) == 1.0 and clamp01(-0.2) == 0.0


def test_refusal_detection() -> None:
    """The refusal heuristic fires on grounded refusals, not on plain assertions."""
    assert looks_like_refusal("No — the Field Belt isn't offered in 36\".")
    assert looks_like_refusal("We don't have a lavender candle in the catalog.")
    assert not looks_like_refusal("The Harbor Throw is $98.00 and measures 130x180 cm.")


def test_judge_registry_defaults_deterministic() -> None:
    """Default EVAL_JUDGE resolves the deterministic judge; the model id is pinned."""
    judge = get_judge()
    assert isinstance(judge, DeterministicJudge)
    assert judge.identity == "deterministic:lexical-overlap-v0"
    # The Claude-when-keys-land default is the latest model, referenced not called.
    assert DEFAULT_JUDGE_MODEL == "claude-opus-4-8"


def test_answerer_registry_defaults_stub() -> None:
    """Default EVAL_ANSWERER resolves the stub answerer."""
    assert isinstance(get_answerer(), StubAnswerer)


def test_unknown_judge_fails_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unknown EVAL_JUDGE raises (never silently degrades to the stub).

    Patches the exact ``settings`` object ``get_judge`` reads (``app.eval.judge.settings``),
    not ``app.core.config.settings`` — the ``seeded_db`` fixture reloads the config module,
    so the module-level binding the function closes over may differ from the reloaded one.
    """
    monkeypatch.setattr("app.eval.judge.settings.eval_judge", "nope")
    with pytest.raises(ValueError, match="Unknown EVAL_JUDGE"):
        get_judge()


def test_unknown_answerer_fails_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unknown EVAL_ANSWERER raises (never silently degrades to the stub).

    Patches ``app.eval.answerer.settings`` for the same module-reload reason as above.
    """
    monkeypatch.setattr("app.eval.answerer.settings.eval_answerer", "nope")
    with pytest.raises(ValueError, match="Unknown EVAL_ANSWERER"):
        get_answerer()


def test_score_record_pure() -> None:
    """score_record produces all four well-formed scores from injected pieces (no DB)."""
    record = GoldenRecord.model_validate(
        {
            "id": "EVAL-TST",
            "question": "How much is the Harbor Throw?",
            "expected_answer": "The Harbor Throw is $98.00.",
            "source_docs": [{"type": "product", "key": "harbor-throw"}],
            "tags": {
                "persona": "buyer",
                "category": "catalog",
                "difficulty": "direct",
                "expects_refusal": False,
            },
            "notes": "",
        }
    )
    result = score_record(
        record,
        gold_context_keys={"harbor-throw"},
        retrieved_context_keys=["harbor-throw", "other-product"],
        retrieved_context_texts=["Harbor Throw $98.00 130x180 cm"],
        answerer=StubAnswerer(),
        judge=DeterministicJudge(),
        k=5,
    )
    assert result.scores.context_recall == 1.0
    # 2 retrieved, k=5 -> denom = min(5, 2) = 2; 1 of them gold -> 0.5 (smoke's formula).
    assert result.scores.context_precision == pytest.approx(1 / 2)
    assert result.answer == "The Harbor Throw is $98.00."  # stub = expected_answer
    assert not result.answer_refused
    for v in (result.scores.response_relevancy, result.scores.faithfulness):
        assert 0.0 <= v <= 1.0


def test_judge_scores_namedtuple() -> None:
    """The deterministic judge returns a well-formed JudgeScores for a refusal sample."""
    record = load_golden()[16]  # EVAL-017 (out-of-catalog refusal) — index 16
    assert record.id == "EVAL-017"
    scores = DeterministicJudge().score(
        record, answer=record.expected_answer, contexts=[]
    )
    assert isinstance(scores, JudgeScores)
    assert 0.0 <= scores.response_relevancy <= 1.0
    assert 0.0 <= scores.faithfulness <= 1.0
