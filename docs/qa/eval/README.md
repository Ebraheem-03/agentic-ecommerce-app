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

This file + validator prove the set is **well-formed and seed-resolvable**. It does
**not** run RAGAS (no agent runtime exists yet). To execute:

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
