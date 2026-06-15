# Eval results — captured smoke artifacts

Machine-readable outputs of the eval smokes (US-QA-D10 onward). These are **captured
baselines**, committed on purpose so progress is reviewable in git.

## `retrieval-smoke-<date>.json` + `retrieval-smoke-latest.json`

Written by `api/tests/qa/test_retrieval_smoke.py` — the no-LLM RAGAS **retrieval-half**
smoke over the product-grounded golden items, against the live keyword `GET /search`.
`retrieval-smoke-latest.json` always points at the most recent run (Echo's Week-4
semantic-retrieval comparison baseline). Dated files are the per-run history.

Each artifact carries: `scores` (mean precision@k / recall@k), `scope` (in-scope vs
policy-only excluded, failing-sample count), per-item precision/recall, and the full
`failing_samples` log (question + expected slugs + retrieved top-k).

**v0 (keyword) headline:** mean precision@5 / recall@5 = **0.000** across 17/25 in-scope
items. This is the EXPECTED keyword result, not a failure — `websearch_to_tsquery` ANDs
every token of a raw natural-language question, so question-phrased queries match nothing.
It is the precise gap semantic retrieval closes; see `docs/qa/eval/README.md` for the
full framing. The smoke is informational, NOT a CI gate.

## `ragas-v1-<date>.{json,md}` + `ragas-v1-latest.*` — **gitignored (run output)**

Written by `api/tests/qa/test_ragas_gate.py` (US-QA-D16, ADR-0033 §3) — the RAGAS gate over
the support-policy answers. ARMED under a live judge (`EVAL_JUDGE=llm`/`claude`); a
deterministic SMOKE otherwise. The dated + `-latest` files are regenerated each run, so they
are gitignored — only this README note stays under version control.

## `agent-eval-<date>.{json,md}` + `agent-eval-latest.*` — **gitignored (run output)**

Written by `api/tests/agent/test_agent_eval_report.py` (US-QA-D17, ADR-0034) — the Day-17
agent eval report. Drives the four ADR-0034 areas through their real seams and emits one
report carrying, per area, **pass/fail · token cost · latency · failing traces**:

- **fallback** — forced-transient cascade to the secondary; domain `APIError` never falls
  back; both exhausted -> canonical `rate_limited` 429 (key-free via `build_failover`).
- **cache** — a normalized/repeated prompt HITS the classifier cache through the real
  LangGraph path; the report SHOWS the cold-LLM vs warm-cache latency + token-cost delta;
  the never-cache guards (injection-fired turn, tool-result turn) + scan-before-lookup hold.
- **merch** — a DRAFT persists (never published) with a comparables price suggestion grounded
  in real seeded rows + its basis, and an injection brief is refused. Structural checks gate;
  the quality score arms only under a live judge (smoke otherwise — honest, not faked green).
- **tool_call** — precision/recall/F1 on tool SELECTION over a scripted multi-turn run, read
  from the authoritative `AgentAction` audit rows (not the stub echo).

The deterministic areas gate in CI key-free; the report regenerates each run, so the dated +
`-latest` files are gitignored — only this note stays. Report types + scoring live in
`api/app/eval/agent_report.py`.
