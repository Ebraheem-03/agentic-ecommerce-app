# Golden Eval Dataset v0 — US-QA-D05

Ground-truth Q&A set for the Hearth agent's RAG layer. Every question is answerable
**strictly from the seed** (`api/app/db/seed/data.py`) — catalog (products/variants/
inventory/reviews) and policies. No invented SKUs, prices, or policy text.

This is the labelled set that catalog/policies **RAGAS** scoring runs against, and the
behavioral spine of the agent eval suite (correct tool choice, out-of-scope refusal,
prompt-injection resistance, regression checks).

- Owners: Juno (driving) · Echo (Week-2 harness) · Sable (seed source-of-truth).
- Status: v0, **revisable**. Acceptance bar = the 5 RAGAS gates in
  `docs/qa/qa-matrix.md` §4 (faithfulness ≥ 0.90 is the headline).

## Format

`golden-v0.jsonl` — **JSONL, one record per line.**

Why JSONL over a single JSON/YAML doc: HuggingFace `datasets` / RAGAS ingest JSONL
natively (`load_dataset("json", data_files=...)`); line-scoped git diffs keep review
sane as the set grows; and a validator can stream + report the exact offending line.

### Record schema

| Field | Type | Notes |
|---|---|---|
| `id` | str | Stable, unique. `EVAL-001`..`EVAL-025`. Never renumber — append. |
| `question` | str | The buyer/support utterance. |
| `expected_answer` | str | The grounded **reference answer**, faithful to source. RAGAS `ground_truth`. |
| `source_docs` | list | Machine-checkable refs into the seed (the "contexts" a faithful answer must rest on). |
| `tags` | object | `persona`, `category`, `difficulty`, `expects_refusal`. |
| `notes` | str | Optional grader hint (which seed fields back the answer). |

### `source_docs` key scheme (resolvable against the live seeded DB)

Each entry is `{"type": ..., "key": ...}` using the **most stable natural key the seed
actually has**:

| `type` | `key` | Resolves to |
|---|---|---|
| `product` | product `slug` | `products.slug` (unique) |
| `variant` | variant `sku` | `variants.sku` (unique) |
| `policy` | `"<kind>@<store_slug>"` or `"<kind>@platform"` | `policies.kind` + joined `stores.slug` (or `store_id IS NULL` for platform) |

Policy `kind` ∈ `returns | shipping | payments | care | platform` (the `policy_kind`
enum, `api/app/db/models/_shared.py`). `@platform` means platform-level
(`policies.store_id IS NULL`).

**Embedding-agnostic by design:** no record references any embedding model, dimension,
or vector. `EMBED_DIM` is Echo's and will change; this set is purely
question → expected-answer → source content.

## Coverage (v0)

25 records, deliberate spread:

- **By persona:** buyer 18 (catalog/inventory/review), support 7 (policy/returns/
  shipping/care). Buyer-heavy by design — catalog Q&A dominates the brand's
  "buying is a conversation" surface.
- **By category:** catalog 12, inventory 4, reviews 1, returns 3, shipping 1,
  payments 1, care 2, policy 1.
- **By difficulty:** direct 11, multi-fact 12, combine 2 (require ≥2 source docs).
- **Refusal items:** 4 (`expects_refusal: true`) — out-of-catalog / out-of-stock /
  out-of-policy. Faithfulness means **not fabricating**: EVAL-008 (no 36" belt size),
  EVAL-015 (no lavender candle), EVAL-017 (no steel water bottle — out of catalog),
  EVAL-025 (no return of an opened bath & body item).
- **Multi-doc cases** (exercise context recall across docs): the 2 `combine` items
  EVAL-021 and EVAL-025 each combine a store-level policy with the platform policy
  (plus a product for EVAL-025); several `multi-fact` items also span a variant pair
  (EVAL-001/002/006/011/012/015).

Mapping to `qa-matrix.md` §2 agent journeys: catalog/inventory/review cases feed
`J-BUY-01/02/03`; refusal cases feed `J-BUY-01` clarify + `J-ADM-03` out-of-scope;
policy cases feed `J-SUP-02` (policy-grounded resolution); return-window edges feed
`J-BUY-06` / `J-SUP-02`.

## How this maps to RAGAS metrics

For each record, the Week-2 harness builds a RAGAS sample:

- `question` ← `question`
- `ground_truth` ← `expected_answer`
- `contexts` ← the chunks the agent actually retrieved (Echo's retriever output)
- `answer` ← the agent's generated answer

Then the §4 gates apply:

| Metric | Gate | What this dataset gives it |
|---|---|---|
| Faithfulness | ≥ 0.90 | Refusal + grounded answers — penalizes any claim not in retrieved context. |
| Answer relevancy | ≥ 0.85 | Direct vs multi-fact questions check the answer addresses the ask. |
| Context precision | ≥ 0.80 | `source_docs` are the gold contexts; precision = retrieved-on-topic. |
| Context recall | ≥ 0.85 | Multi-doc (`combine`) cases ensure all needed docs are retrieved. |
| Answer correctness *(opt)* | ≥ 0.80 | `expected_answer` is the labelled truth for semantic+factual match. |

## What Echo must add in Week 2 to execute this

> **Status (US-E7-00, Day-13): the harness now EXISTS** — `api/app/eval/` +
> `api/tests/qa/test_ragas_harness.py`. It scores all four metrics (context precision/
> recall + response relevancy + faithfulness) over this golden set and writes a score
> artifact (`results/ragas-<date>.json` + `ragas-latest.json`, gitignored). The default
> path is **deterministic + CI-safe** (no LLM keys, no network): precision/recall are
> set-overlap math; the judge metrics run behind a `Judge` seam whose default is a
> `DeterministicJudge` lexical stub (a *harness-exercising stub, not a semantic judge*),
> and the per-question answer comes from a `StubAnswerer` (no live agent runtime yet).
> **Pending keys:** a real Claude eval JUDGE (`EVAL_JUDGE`, default model
> `claude-opus-4-8`) and the real agent ANSWERER (`EVAL_ANSWERER`) each register in one
> place and swap with one setting — no harness change. The §4 quality gates below only
> bind under a real judge. See **ADR-0030**.

This file + validator prove the set is **well-formed and seed-resolvable**. The original
plan to execute it (now partially DONE by the harness above):

1. **Retriever** over the seeded `embeddings` (product + policy sources) returning
   chunks tagged back to product `slug` / policy `kind@store`, so retrieved contexts
   line up with `source_docs` for context-precision/recall scoring.
2. **A RAGAS runner** that loads `golden-v0.jsonl`, calls the agent per `question`,
   collects `answer` + `contexts`, and scores against the §4 thresholds. Free-tier
   Groq/Gemini as the judge LLM (keep it model-agnostic here).
3. **Refusal assertion**: for `expects_refusal: true`, additionally assert the agent
   declines / says "not available" rather than fabricating — this is a behavioral
   gate beyond the numeric RAGAS score.
4. Wire the runner into CI alongside the E2E gate; block agent merges to `dev` on any
   metric below threshold or any refusal regression.

## Retrieval smoke (US-QA-D10) — the no-LLM retrieval-half baseline

Before the RAGAS judge half exists, `api/tests/qa/test_retrieval_smoke.py` runs a
**deterministic, no-LLM** retrieval-quality smoke against the LIVE keyword `GET /search`
(Postgres FTS, `ts_rank`) over the seeded catalog. It is the *retrieval half* of RAGAS —
context **precision@k** / **recall@k** computed by checking whether each golden question's
ground-truth `source_docs` products appear in the top-k results — with **no judge LLM**.

- **Scope:** only **product-grounded** golden items (those whose `source_docs` cite a
  `product` slug or a `variant` sku → its product). **Policy** source_docs are NOT in the
  product catalog; policy/RAG retrieval is Echo's agent-RAG surface (Week-4) and is
  *excluded*, not failed. v0: 17/25 items in scope, 8 policy-only excluded.
- **Metrics:** `recall@k = |relevant ∩ topk| / |relevant|`,
  `precision@k = |relevant ∩ topk| / min(k, n_retrieved)`, k=5. Means aggregated.
- **It is a SMOKE, not a CI gate.** `websearch_to_tsquery` ANDs every token of the input,
  so feeding a raw natural-language *question* matches ~nothing: **keyword question-recall
  is ~0 by construction**. That is the captured finding — the exact gap semantic retrieval
  (Echo, Decision-4) closes — not a failure. The test asserts only that the smoke RAN and
  produced/logged well-formed scores; a separate liveness anchor proves keyword search DOES
  recall the right product from a distinctive single *term*.
- **Captured artifact:** `docs/qa/eval/results/retrieval-smoke-<date>.json` (+ a stable
  `retrieval-smoke-latest.json`): scores, scope counts, per-item precision/recall, and the
  full failing-sample log (question + expected slugs + retrieved top-k).

**Hand-off to Echo (Week-4):** this smoke is the retrieval-half baseline. When semantic /
pgvector retrieval lands (the `mode=semantic` swap), re-run the SAME smoke and compare
against `retrieval-smoke-latest.json` — the question-level recall it lifts off ~0 is the
measure of the semantic win. The faithfulness / answer-relevancy half (the judge-LLM gates
in the table above) is the other half Echo adds on top.

Run: `cd api && DATABASE_URL=... pytest tests/qa/test_retrieval_smoke.py -s -v`

## Validator

`api/tests/qa/test_golden_eval.py`:

- Static checks: count == 25, unique non-empty `id`s, required fields present,
  tags from the controlled vocab, ≥1 refusal item.
- **Seed-resolve check** (DB-backed): reuses Sable's `migration_db` throwaway-DB
  fixture (`api/tests/db/conftest.py`), migrates to head, runs the seed, then asserts
  **every** `source_docs` entry resolves to a real row (product slug / variant sku /
  policy kind+store). This guarantees the golden set never drifts from the seed.
  Skips cleanly (like the other DB tests) when no `TEST_DATABASE_URL`/`DATABASE_URL`
  is set — but the static checks always run.

Run: `cd api && pytest tests/qa/test_golden_eval.py -v`

## RAGAS gate v1 (US-QA-D16, ADR-0033 §3)

`api/app/eval/gate.py` + `api/tests/qa/test_ragas_gate.py` are the **v1 gate** that puts the
ADR-0033 §3 floors on the **support-policy** answers: faithfulness ≥ 0.90 · answer
relevancy ≥ 0.80 · context recall ≥ 0.70, plus every `expects_refusal` policy item must
refuse and the injection test must pass.

- **Armed vs smoke.** The numeric floors are **ARMED only when a live judge is configured**
  (`EVAL_JUDGE=claude` + an Anthropic key — the human's LOCAL run). In CI / default (no key)
  the gate falls back to the deterministic stub as a **SMOKE**: the floors are computed +
  reported but do NOT hard-fail (the stub is lexical, not semantic). The arming decision is
  explicit in the report (`armed`, `judge`). Same key-free pattern Day-15 set.
- **Real grounded answers.** The gate scores answers from the **real support-policy RAG
  path** (the live LangGraph support node), key-free via Echo's injectable `SupportBrain` —
  not the `StubAnswerer`. So faithfulness/recall reflect the actual grounded pipeline.
- **Deterministic checks gate in CI.** Refusal-correctness + injection (driven through the
  real guardrail path, asserting `action_type="guardrail"`, `outcome=refused`) need no judge.
- **Claude judge.** Wired behind the existing `"claude"` registry slot in `app/eval/judge.py`
  (model `claude-opus-4-8`); a real Anthropic call when a key is present, referenced-but-not
  -constructed (lazy SDK import) key-free.
- **Known keyword gap.** EVAL-025 (a multi-policy return question) is mis-ranked by the
  key-free **keyword** policy retriever and does NOT refuse under it — recorded as a tracked
  `refusal:known-keyword-gap` defect (visible, counted) but NOT hard-failing CI, the same
  lexical gap semantic retrieval closes. The armed/semantic run must flip it to a refusal.

Artifacts (gitignored, like the smoke/regression/agent-convo reports — only this README note
is committed): `docs/qa/eval/results/ragas-v1-<date>.{json,md}` + a stable `ragas-v1-latest`.
The MD shows per-metric means vs floors, armed/smoke + which judge, the refusal log, the
injection result, and any defects.

Run: `cd api && DATABASE_URL=... pytest tests/qa/test_ragas_gate.py -v`

**Layer split (do not re-assert):** Echo owns the guardrail/RAG/support ATOMS
(`tests/agent/test_guardrails.py`, `test_support_agent.py` — refund tiers, the injection
regex table, policy grounding/citation mechanics). The Day-13 harness owns the
RUNS-and-well-formed sample (`test_ragas_harness.py`). This gate owns only the §3 FLOORS +
the armed-vs-smoke arming logic + the system-level refusal/injection acceptance bar.
