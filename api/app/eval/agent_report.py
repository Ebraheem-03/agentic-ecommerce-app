"""Day-17 agent eval report — fallback · cache · merch draft · tool-call F1 (US-QA-D17).

THE REPORT MODEL (the deliverable's shape)
==========================================
ADR-0034's "Consequences" scopes a single readable eval report covering FOUR areas, each
carrying **pass/fail, token cost, latency, and any failing traces**:

  1. ``fallback``  — provider failover: a forced TRANSIENT error on the primary cascades to
     the secondary; a DOMAIN error never falls back; both exhausted -> a canonical
     ``rate_limited`` 429. Deterministic -> gates in CI key-free.
  2. ``cache``     — semantic-cache hit: a repeated/normalized prompt HITS the (stub
     exact-match tier) cache; the report SHOWS the cold-LLM vs warm-cache latency + token
     delta; the NEVER-cache guards (injection-fired turn, tool-result turn) hold; the
     scan-before-lookup ordering holds. Deterministic -> gates in CI key-free.
  3. ``merch``     — merchandising draft quality: a DRAFT is produced (never published), the
     comparables price suggestion is grounded in real seeded rows with its basis, injection
     is refused. The structural checks gate in CI; the QUALITY score arms only under a live
     judge (``EVAL_JUDGE=llm``/``claude``), smoke otherwise (honest, not faked green).
  4. ``tool_call`` — tool-call F1: precision / recall / F1 on tool SELECTION over a scripted
     multi-turn run, computed from the authoritative ``AgentAction`` audit rows (not the
     stub echo). Deterministic -> gates in CI key-free.

This module owns only the REPORT TYPES + the rendering/serialization + the small scoring
helpers (token-cost estimate, F1, merch quality). The test
(``tests/agent/test_agent_eval_report.py``) DRIVES the real seams (the failover policy, the
LangGraph cache path, the merch node, the audit trail) and assembles a ``D17EvalReport``
from the live evidence — mirroring how the RAGAS gate's test drives ``run_gate``.

LAYER SPLIT (no overlap with Echo's atoms)
==========================================
Echo's unit tests (``test_llm_failover.py`` / ``test_semantic_cache.py`` /
``test_merch_agent.py``) own the ATOMS and STAND — this report does NOT re-assert them. The
report layer is the cross-cutting EVAL NUMBERS + the journey-level evidence: the latency/cost
DELTA the cache buys, the tool-selection F1 over a stitched conversation, the armed-vs-smoke
merch quality number, and the failover cascade proven end-to-end through ``build_failover``.

ARMED vs SMOKE (the Day-16 convention)
======================================
The deterministic areas (fallback, cache, tool-call F1, merch never-publish/refusal) gate in
CI key-free. The merch QUALITY score is the only judged number: it arms under a live judge
(``is_armed``) and is reported-but-not-gating under the deterministic stub — the honest
"not faked green" posture. ``D17EvalReport.passed`` is true iff there are no HARD defects.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

# api/app/eval/agent_report.py -> parents[3] == repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "docs" / "qa" / "eval" / "results"

# Merch draft-quality floor (armed only under a live judge — Day-16 convention).
MERCH_QUALITY_FLOOR = 0.70


# --------------------------------------------------------------------------- #
# Token-cost estimate — a deterministic, provider-agnostic proxy.               #
# --------------------------------------------------------------------------- #
# We do NOT call a live provider in CI, so "token cost" is a deterministic ESTIMATE: a
# whitespace token count of the prompt the LLM call WOULD send. The point of the metric is
# the DELTA — a cache HIT sends 0 prompt tokens to the LLM (the round-trip is skipped), a
# cold MISS sends the full prompt — so the report can show the saving honestly without a key.
def estimate_tokens(text: str) -> int:
    """A deterministic token-count proxy (whitespace words). 0 for empty/None-ish input."""
    if not text:
        return 0
    return len(re.findall(r"\S+", text))


# --------------------------------------------------------------------------- #
# Precision / recall / F1 over tool SELECTION (multiset).                        #
# --------------------------------------------------------------------------- #
def _multiset_intersection(a: list[str], b: list[str]) -> list[str]:
    """Multiset intersection preserving multiplicity (a doubled expected needs two actuals)."""
    out: list[str] = []
    pool = list(b)
    for x in a:
        if x in pool:
            pool.remove(x)
            out.append(x)
    return out


class F1Score(BaseModel):
    """Precision / recall / F1 on tool SELECTION over a run, with the raw sequences."""

    model_config = ConfigDict(frozen=True)

    expected: list[str]
    actual: list[str]
    true_positives: int
    precision: float = Field(ge=0.0, le=1.0)
    recall: float = Field(ge=0.0, le=1.0)
    f1: float = Field(ge=0.0, le=1.0)


def tool_call_f1(expected: list[str], actual: list[str]) -> F1Score:
    """Compute precision/recall/F1 on tool SELECTION (multiset match).

    ``actual`` MUST come from the executor's ``AgentAction`` audit rows (the authoritative
    record of what really ran), never the scripted plan echoing itself. Precision = TP/|actual|,
    recall = TP/|expected|, F1 the harmonic mean. Empty actual+expected -> a perfect 1.0
    (vacuously correct: nothing expected, nothing ran).
    """
    tp = len(_multiset_intersection(expected, actual))
    precision = tp / len(actual) if actual else (1.0 if not expected else 0.0)
    recall = tp / len(expected) if expected else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return F1Score(
        expected=expected,
        actual=actual,
        true_positives=tp,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
    )


# --------------------------------------------------------------------------- #
# Merch draft-quality score — deterministic smoke (arms under a live judge).     #
# --------------------------------------------------------------------------- #
def merch_quality_smoke(
    *, title: str, description: str, attributes: dict[str, str], basis: str
) -> float:
    """A deterministic, lexical merch-draft quality PROXY (NOT a semantic judge).

    Like the RAGAS ``DeterministicJudge``, this is a harness-exercising stub: it scores
    structural completeness (a non-empty title/description, some attributes, a price basis
    that names its comparables) so the report carries a number on the key-free CI path. It
    is NOT a quality verdict — the real number arms under the ``"llm"``/``"claude"`` judge.
    Bounded to ``[0, 1]``.
    """
    checks = (
        bool(title.strip()),
        len(description.split()) >= 6,
        bool(attributes),
        "median" in basis.lower() or "comparable" in basis.lower(),
    )
    return round(sum(checks) / len(checks), 4)


# --------------------------------------------------------------------------- #
# Report types — one per area + the roll-up.                                     #
# --------------------------------------------------------------------------- #
class Defect(BaseModel):
    """A tracked failing trace (clear, not silent). ``kind`` pins WHAT failed."""

    model_config = ConfigDict(frozen=True)

    area: str
    kind: str
    detail: str
    hard: bool = True


class AreaResult(BaseModel):
    """One eval area's pass/fail + cost/latency + its failing traces.

    ``token_cost`` and ``latency_ms`` are the area's headline numbers (e.g. the cold-vs-warm
    deltas for the cache area). ``metrics`` carries the area-specific scalars (F1, the merch
    quality score, the cascade attempt counts) for the JSON consumer.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    passed: bool
    summary: str
    token_cost: dict[str, float] = Field(default_factory=dict)
    latency_ms: dict[str, float] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    traces: list[Defect] = Field(default_factory=list)


class D17EvalReport(BaseModel):
    """The Day-17 agent eval report — four areas, armed/smoke, pass/fail + failing traces."""

    model_config = ConfigDict(frozen=True)

    story: str = "US-QA-D17"
    armed: bool
    judge_identity: str
    areas: list[AreaResult]

    @property
    def defects(self) -> list[Defect]:
        return [t for a in self.areas for t in a.traces]

    @property
    def hard_defects(self) -> list[Defect]:
        return [d for d in self.defects if d.hard]

    @property
    def passed(self) -> bool:
        """The report passes iff no area carries a HARD failing trace.

        The merch QUALITY miss is a SOFT trace under the deterministic smoke (reported, not
        gating); it becomes hard only when armed. Every deterministic area's miss is hard.
        """
        return not self.hard_defects

    def area(self, name: str) -> AreaResult:
        return next(a for a in self.areas if a.name == name)


# --------------------------------------------------------------------------- #
# Rendering — readable Markdown (the human-facing half of the artifact).        #
# --------------------------------------------------------------------------- #
def _fmt_kv(d: dict[str, float]) -> str:
    return ", ".join(f"{k}={v:g}" for k, v in d.items()) if d else "—"


def render_markdown(report: D17EvalReport, *, generated_at: str) -> str:
    """Render the report as a readable Markdown summary (the human-facing artifact)."""
    mode = (
        "ARMED (live judge — merch quality gates)"
        if report.armed
        else "SMOKE (deterministic — merch quality reported, not gating)"
    )
    lines: list[str] = [
        "# Agent eval report — Day 17 (US-QA-D17, ADR-0034)",
        "",
        f"- Generated: {generated_at}",
        f"- Mode: **{mode}**",
        f"- Judge: `{report.judge_identity}`",
        f"- Gate: **{'PASS' if report.passed else 'DEFECTS'}** "
        f"({len(report.hard_defects)} hard / {len(report.defects)} total failing trace(s))",
        "",
        "## Areas",
        "",
        "| Area | Pass | Token cost | Latency (ms) | Metrics | Summary |",
        "|---|---|---|---|---|---|",
    ]
    for a in report.areas:
        lines.append(
            f"| {a.name} | {'PASS' if a.passed else 'FAIL'} | {_fmt_kv(a.token_cost)} | "
            f"{_fmt_kv(a.latency_ms)} | {_fmt_kv(a.metrics)} | {a.summary} |"
        )
    lines += ["", "## Failing traces", ""]
    if report.defects:
        lines += ["| Area | Kind | Hard | Detail |", "|---|---|---|---|"]
        for d in report.defects:
            lines.append(
                f"| {d.area} | {d.kind} | {'yes' if d.hard else 'no (smoke)'} | {d.detail} |"
            )
    else:
        lines.append("_None._")
    if not report.armed:
        lines += [
            "",
            "> SMOKE run: the merch draft-quality number is a deterministic lexical proxy, "
            "not a semantic judge, so it is REPORTED but does NOT gate. It arms (and the "
            f"floor {MERCH_QUALITY_FLOOR} hard-fails on a miss) only under a live judge "
            "(`EVAL_JUDGE=llm`/`claude`). The fallback cascade, the cache hit + its "
            "latency/cost delta + the never-cache guards, and the tool-call F1 all gate in "
            "CI key-free regardless.",
        ]
    lines.append("")
    return "\n".join(lines)


def write_report_artifact(
    report: D17EvalReport, *, results_dir: Path | None = None, prefix: str = "agent-eval"
) -> tuple[Path, Path]:
    """Write the dated + ``-latest`` report artifacts (JSON + MD); return (json, md) paths.

    Gitignored (``docs/qa/eval/results/<prefix>-*``), like the RAGAS/smoke/regression
    artifacts — only the committed README note stays under version control. ``prefix``
    lets distinct report families (Day-17 ``agent-eval`` vs Day-23 ``agent-eval-suite``)
    write side-by-side without clobbering each other's ``-latest``.
    """
    out_dir = results_dir or RESULTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC)
    generated_at = stamp.isoformat()
    date = stamp.strftime("%Y-%m-%d")

    payload = {"generated_at": generated_at, **report.model_dump()}
    json_text = json.dumps(payload, indent=2, default=str) + "\n"
    md_text = render_markdown(report, generated_at=generated_at)

    dated_json = out_dir / f"{prefix}-{date}.json"
    dated_md = out_dir / f"{prefix}-{date}.md"
    dated_json.write_text(json_text, encoding="utf-8")
    dated_md.write_text(md_text, encoding="utf-8")
    (out_dir / f"{prefix}-latest.json").write_text(json_text, encoding="utf-8")
    (out_dir / f"{prefix}-latest.md").write_text(md_text, encoding="utf-8")
    return dated_json, dated_md


def all_tools(*sequences: Iterable[str]) -> list[str]:
    """Flatten tool-name sequences into one ordered list (test convenience)."""
    out: list[str] = []
    for seq in sequences:
        out.extend(seq)
    return out


# =========================================================================== #
# US-E7-05 (ADR-0042 §D3) — goal accuracy + loop-termination scoring.          #
# =========================================================================== #
# These extend the Day-17 report layer (same AreaResult/Defect shapes) with the two
# Day-23 structural metrics. Both are DETERMINISTIC over scripted journeys, so they HARD-
# GATE in CI key-free (the ADR-0042 §D3 posture); the live-LLM goal accuracy + the RAGAS
# numeric floors arm only on the local live-judge run (the existing ``is_armed`` seam).

# The intended terminal outcome for a scripted journey (what "reaching the goal" means).
GoalOutcome = str  # "checkout_proposed" | "refusal" | "cited_answer" | "reply"


class GoalResult(BaseModel):
    """One journey's goal-accuracy verdict: did the agent reach the INTENDED outcome?"""

    model_config = ConfigDict(frozen=True)

    journey: str
    intent: str
    expected: GoalOutcome
    actual: GoalOutcome
    reached: bool


def classify_outcome(
    *,
    final_text: str,
    action: dict[str, object] | None,
    awaiting_approval: bool,
    citations: list[dict[str, object]] | None,
) -> GoalOutcome:
    """Deterministically classify a turn's terminal outcome from its structural signals.

    The SAME taxonomy the runtime trace uses (ADR-0042 §D1), derived structurally (never a
    lexical scan of the reply): an approval pause -> ``checkout_proposed``; a refused-outcome
    action -> ``refusal``; a grounded answer with citations -> ``cited_answer``; otherwise a
    plain ``reply``. The ``"I wasn't able to finish that"`` fallback is a non-goal ``reply``
    here (loop-termination is the metric that catches a fallback; see ``terminated_in_budget``).
    """
    if awaiting_approval:
        return "checkout_proposed"
    if isinstance(action, dict) and action.get("outcome") == "refused":
        return "refusal"
    if citations:
        return "cited_answer"
    return "reply"


def goal_accuracy(results: list[GoalResult]) -> float:
    """Fraction of journeys that reached their intended goal (1.0 == all reached)."""
    if not results:
        return 1.0
    return round(sum(1 for r in results if r.reached) / len(results), 4)


# The graceful step-budget fallback string (mirrors graph.py). A shopping journey that
# ends on this did NOT terminate cleanly within budget — the DEFECT-D22-01 signal.
FALLBACK_MARKER = "I wasn't able to finish that"


def terminated_in_budget(*, final_text: str, awaiting_approval: bool) -> bool:
    """True iff a shopping journey terminated with a real reply / checkout proposal.

    The loop-termination metric (ADR-0042 §D2/§D3): a turn that ends on the graceful
    step-budget fallback string did NOT terminate cleanly — that is the live planner loop
    DEFECT-D22-01 the loop-guard fixes. A checkout proposal (approval pause) is a clean
    terminal; any non-fallback reply is too.
    """
    if awaiting_approval:
        return True
    return FALLBACK_MARKER not in final_text


__all__ = [
    "FALLBACK_MARKER",
    "MERCH_QUALITY_FLOOR",
    "AreaResult",
    "D17EvalReport",
    "Defect",
    "F1Score",
    "GoalResult",
    "all_tools",
    "classify_outcome",
    "estimate_tokens",
    "goal_accuracy",
    "merch_quality_smoke",
    "render_markdown",
    "terminated_in_budget",
    "tool_call_f1",
    "write_report_artifact",
]
