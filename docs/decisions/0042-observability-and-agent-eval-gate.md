# ADR-0042 — Observability substrate, planner loop-guard, and the agent-eval gate posture

- **Status:** Accepted (human-ratified up front, Day 23 / W4D2, 2026-07-01)
- **Supersedes/extends:** ADR-0031 (injectable scripted brains), ADR-0033 §3 (armed-vs-smoke eval), ADR-0041 (DEFECT-D22-01 deferral)
- **Stories:** US-E7-04 (tracing/observability), US-E7-05 (agent eval suite, `[REVIEW]`), US-QA-D23 (observability E2E)

## Context
Day 22 flipped the buyer money-path fully live and filed **DEFECT-D22-01**: under the real
Groq model the `LLMShoppingPlanner` (`with_structured_output(PlannerStep)`) re-issues the
*identical* `search(...)` every step in the `_shopping_node` plan-execute loop
(`api/app/agent/graph.py:240-260`), never flipping to `reply`, exhausting `MAX_PLAN_STEPS=6`
→ graceful fallback. The bug is **masked in CI** because every agent test injects scripted
brains (ADR-0031). Day 23 builds the observability + eval layer where this is instrumented,
caught, and gated.

## Decisions (3)

### D1 — Observability substrate: **local structured trace store** (not external SaaS)
Per-agent-run traces (`trace_id`, `run_id`, per-node, tool calls, prompt, `tokens_in/out`,
`cost_usd`, `latency_ms`) are written to a **self-contained local store**
(`docs/qa/obs/results/<run>.jsonl`, gitignored — same convention as the eval/agent
artifacts). **No external SaaS, no API key, no prompt/PII off-box** — preserves the
key-free CI invariant. A **dormant LangSmith seam** is left in place (one env flag) for a
future hosted run, but the default and CI path are fully local. Rejected: LangSmith
(external key + data egress) and Langfuse (extra compose service to maintain).

### D2 — DEFECT-D22-01 fix: **loop-guard (real fix) + provider evaluation** ("Both")
The primary fix is a **provider-agnostic loop-guard** in the plan-execute loop:
- track issued tool calls; an **identical** re-issued call is **not re-executed**;
- once `tool_results` exist and a step makes **no progress** (only repeats), **force a reply**.
A scripted **"looping brain" regression test** locks this in CI forever (the loop is
reproducible key-free once the guard exists). Separately, the **live eval lane evaluates
the provider**; the default `LLM_PROVIDER` is swapped (Groq→Gemini) **only if the live eval
prefers it** — the loop-guard is the fix regardless of provider, the swap is conditional.

### D3 — Eval gate posture (US-E7-05 `[REVIEW]`): **structural hard-gates CI; numeric floors arm local**
Consistent with ADR-0033 §3 (armed-vs-smoke) and the key-free CI invariant:
- **HARD-GATE in CI, key-free (deterministic / scripted brains):** tool-call accuracy/F1,
  the **loop-termination guard**, **goal accuracy** over scripted journeys, refusal +
  injection gating.
- **ARM only on the local live-judge run** (`EVAL_JUDGE=llm` + the free-tier Groq/Gemini key,
  no Anthropic key per US-E7-EJ): RAGAS numeric floors (faithfulness ≥0.90 · relevancy ≥0.80
  · recall ≥0.70) and **live-LLM goal accuracy**.
- CI proves the agent **terminates and selects the right tools**; the quality floors bind on
  the human's local armed run. Running the live LLM in CI (with a key in secrets, hard-failing
  on non-deterministic floors) is **rejected** — it breaks key-free CI and is flaky/cost-bearing
  on a free tier.

## Consequences
- US-E7-04/05 + US-QA-D23 run `[AFK]` to this ADR (US-E7-05's `[REVIEW]` is ratified up front,
  the Day 15-17 pattern).
- DEFECT-D22-01 closes with a CI-gated regression; the headline agentic shopping surface
  terminates under the real LLM.
- Every failing E2E/RAGAS case can link to its trace (prompt + tool calls + tokens + cost) by
  `run_id` (US-QA-D23).

## As-built (Day 23, Echo)

### D1 — trace store (`api/app/agent/trace.py`)
- One `RunTrace` per turn, written to `docs/qa/obs/results/<run_id>.jsonl` (gitignored).
  Captures node spans, tool calls (at the `execute_tool` audit chokepoint), model calls
  (the brain `*.invoke` seam — prompt + usage + latency), and the disposition.
- **Ambient contextvar** (`_current_trace`) is the instrumentation seam: the runner opens
  the trace per turn; nodes/executor/brains write through tiny best-effort helpers that are
  a **no-op** outside a traced run. No node/executor signature changed. Wrapped so a tracing
  fault never breaks a turn.
- Cost via `_PRICE_TABLE` (USD/1M tokens, provider:model with a `provider:*` fallback).
  Groq/Gemini free-tier rows are `0.0`; an example paid `anthropic:*` row proves the math.
  Scripted-brain turns (CI) record **null tokens / 0 cost** gracefully (no model call).
- Config: `OBS_ENABLED` (default true; false = pure no-op) + `OBS_BACKEND=local|langsmith`.
  LangSmith is a **dormant seam** — no hard dep; selecting it logs once and degrades to local.

### D2 — loop-guard (`_shopping_node`, `api/app/agent/graph.py`)
- **Provider-agnostic, real fix.** The loop now tracks issued tool calls by a normalized
  signature; an identical re-issued call is **not re-executed**; once results exist and a
  step makes **no progress** (only repeats), it **forces a grounded reply synthesized from
  the existing tool results** instead of looping into the generic step-budget fallback.
- Locked by a key-free scripted **`LoopingPlanner`** regression
  (`tests/agent/test_orchestrator.py::test_looping_planner_terminates_with_real_reply`):
  the identical search runs exactly once, the turn ends with a real reply (NOT the
  `"I wasn't able to finish that"` fallback), planner consulted ≤2 steps (< `MAX_PLAN_STEPS`).
- **DECISION (needs the human's live armed run):** the loop-guard is the fix **regardless of
  provider** — `LLM_PROVIDER` default is UNCHANGED (Groq). The Groq↔Gemini comparison needs
  live keys (not in CI); swap the default **only if** the human's live eval prefers Gemini.
  This is a **local armed** decision, intentionally not taken blind here.

### D3 — eval suite (`api/app/eval/agent_report.py` + `tests/agent/test_agent_eval_suite.py`)
- Adds **goal accuracy** (buy→checkout_proposed, injection→refusal, policy→cited_answer —
  scored structurally via the trace taxonomy, not a lexical scan) and **loop-termination**
  (every shopping journey, incl. the looping planner, terminates within budget) as new
  `AreaResult`s; **tool F1** folds in from Day 17. All three are deterministic / key-free and
  HARD-GATE in CI. RAGAS numeric floors + live-LLM goal accuracy stay behind the `is_armed`
  seam (ADR-0033 §3) — unchanged. Report artifact: `agent-eval-suite-*` (distinct prefix so
  it does not clobber the Day-17 `agent-eval-*` report).
