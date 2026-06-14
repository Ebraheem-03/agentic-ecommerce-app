# ADR-0030 — RAGAS evaluation harness: deterministic CI-safe default, pluggable judge/answerer seams

- Status: accepted
- Date: 2026-06-14
- Owner: Echo (AI/Agents)
- Stories: US-E7-00 (RAGAS harness implementation)
- Relates: ADR-0026 (embedding provider seam), ADR-0027 (search keyword-live/semantic seam),
  US-QA-D05 (golden eval set), US-QA-D10 (no-LLM retrieval smoke)

## Context

The golden eval set (`docs/qa/eval/golden-v0.jsonl`, 25 records) and the Day-10
retrieval smoke give us the *retrieval half* of RAGAS (context precision/recall against
live keyword search, no LLM). This story adds the harness that scores **all four**
headline metrics — context precision, context recall, response relevancy, faithfulness —
and writes a score artifact, with a **CI-safe sample run**.

Two hard constraints shaped the design:

1. **CI must run with NO LLM keys and NO network.** The runtime product LLM (Groq/Gemini
   free-tier) and any eval-judge key are still open human decisions. CI cannot wait on
   them.
2. **Provider-agnostic, no heavy deps.** Per CLAUDE.md the default path must hardcode no
   provider, and we will not add a `ragas`/LLM dependency just to make CI green.

## Decisions

### 1. New offline library `api/app/eval/` (mirrors the embedding/retriever house seams)

`dataset.py` (typed Pydantic v2 `GoldenRecord` loader + centralised JSONL parsing),
`metrics.py` (the deterministic set-overlap math + lexical helpers), `answerer.py`
(answer-source seam), `judge.py` (LLM-judge-metric seam), `harness.py` (score one record
→ four metrics + means), `runner.py` (DB-aware orchestration + artifact writer). It is
**offline tooling** — it touches no request path, raises plain `ValueError` (not
`APIError`), and depends only on the stdlib + what's already in the venv.

### 2. Deterministic default = CI-safe; real judge is a one-line swap

- **Context precision/recall** are computed by pure set-overlap (`metrics.py`), the SAME
  formula the retrieval smoke uses — factored into one shared helper so the smoke and the
  harness can't drift. These need **no judge**.
- **Response relevancy/faithfulness** are the LLM-judge metrics, behind a `Judge`
  Protocol. The default `DeterministicJudge` derives reproducible `[0,1]` scores from
  lexical/source-overlap heuristics. It is explicitly a **harness-exercising stub, not a
  semantic judge** — its numbers prove the pipeline ran and is well-formed, NOT that an
  answer is good. The §4 qa-matrix quality gates only bind under a real judge.
- A registry (`_JUDGES` + `get_judge()` resolving `settings.eval_judge`, default
  `"deterministic"`) mirrors `get_embedder()`/`get_retriever()`: unknown judge → fails
  loud, never silently degrades. Same shape for the answerer (`_ANSWERERS` +
  `get_answerer()` + `EVAL_ANSWERER`, default `"stub"`).

### 3. Stub answerer (no live agent runtime yet)

The judge metrics need an `answer` per question. No agent SSE loop exists yet, so the
default `StubAnswerer` returns the record's labelled `expected_answer` — a faithful,
on-topic stand-in that keeps the judge metrics well-formed and reproducible. It is HONEST
about being a stub (`identity = "stub:expected-answer"`); it is NOT a model output. The
real agent answerer plugs into the same seam (`EVAL_ANSWERER`) when it lands. We chose
"derive from expected_answer" over "answer purely from retrieved contexts" because, with
stub embeddings + keyword-only retrieval, raw-question recall is ~0 by construction (the
captured smoke finding), so a retrieval-only stub answer would be near-empty for most
items and the judge metrics would be meaningless.

### 4. Claude as the eval JUDGE when keys land (separate from the product LLM)

Per CLAUDE.md, the eval JUDGE is **separate** from the runtime product LLM (which stays
Groq/Gemini free-tier). When a judge key lands, a `ClaudeJudge` registers under `"claude"`
and defaults to the **latest Claude model** — `DEFAULT_JUDGE_MODEL = "claude-opus-4-8"`.
That id appears ONLY as the registered default of the not-yet-active Claude provider;
nothing in the default path imports or calls it. **This is the open `[REVIEW]`/
`[DECISION]`:** confirm Claude as the eval judge and the exact model id before wiring.

### 5. No hard `ragas` dependency

The deterministic path is pure-Python (stdlib + venv). A real `ragas` integration would
slot in behind the SAME `Judge` Protocol (wrap RAGAS's metric callables in a registered
judge that needs keys) — documented in `judge.py`, not wired. Pulling `ragas` (with its
LLM-client transitive deps) just to run CI deterministically would contradict the no-deps
constraint and add a network/key surface to the default path.

### 6. Score artifact, gitignored

`runner.write_artifact` writes `docs/qa/eval/results/ragas-<date>.json` + a stable
`ragas-latest.json`: per-item four scores + means + judge/answerer identity (so a
deterministic vs real run is distinguishable) + scope counts + refusal log. These are
gitignored (`docs/qa/eval/results/ragas-*.json`) exactly like the Day-10 retrieval-smoke
artifacts, so wall-clock-stamped files never churn CI.

### 7. Refusal awareness (signal, not a gate)

For `tags.expects_refusal: true` items the harness records whether the (stub) answer
refused (`looks_like_refusal` heuristic) and surfaces it in the artifact's `refusal_log`.
v0 does NOT hard-gate on it — it is a behavioural signal beyond the numeric score, to be
promoted to a gate once a real answerer lands.

## Consequences

- CI runs the full four-metric harness with no keys/network; the sample run asserts the
  harness RAN and is well-formed (means in `[0,1]`, artifact written, real in-scope
  subset covered, refusals logged), NOT quality thresholds on stub scores — same honesty
  as the smoke ("smoke, not a gate").
- Deterministic sample run (this commit): context precision/recall ≈ 0.0 (the expected
  raw-question keyword gap — what semantic retrieval, Echo Week-4, closes), response
  relevancy ≈ 0.61, faithfulness ≈ 1.0 (stub answer fully grounded against the
  ground-truth backstop). All 4 `expects_refusal` items detected refusing.
- When the embedding/semantic seam (ADR-0026/0027) and a real judge/answerer land, only
  `EMBED_PROVIDER` / `_ACTIVE_MODE` / `EVAL_JUDGE` / `EVAL_ANSWERER` flip — no harness
  code change — and the same artifact becomes the real-quality baseline.
