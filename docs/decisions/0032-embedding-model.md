# ADR-0032 — Embedding model: hosted Gemini @ 768 (as-built)

- Status: Accepted
- Date: 2026-06-15
- Owner: Echo (AI / Agents)
- Story: US-E5-04b (implement the real embedding provider behind the seam)
- Supersedes: the open `[DECISION]` left in ADR-0026 §Decision-4 (provider seam) and
  the `EMBED_DIM` deferral in ADR-0026 §Decision-4 / ADR-0018.

## Context

ADR-0026 shipped a pluggable `Embedder` seam (`app/services/embeddings.py`) with a
deterministic `StubEmbedder` default, leaving the real model an open human decision tied to
the free-tier key. Echo's written analysis
(`docs/data/embedding-recommendation.md`) laid out two viable options:

1. **Self-hosted `BAAI/bge-small-en-v1.5` @384** (Echo's top pick) — key-free / offline
   semantic search in CI, but needs a model in the image and a schema migration (768→384).
2. **Hosted Gemini `gemini-embedding-001` @768** (Echo's 2nd pick) — zero infra, no
   migration (768 stays), higher quality ceiling, but needs a live key, so CI/evals stay
   on the stub.

## Decision

**The human ratified option 2: hosted Gemini, `EMBED_DIM = 768`.** Rationale (the human's
call): the Gemini key is already live (used by the chat layer, ADR-0031), zero added infra,
no model weights in the image, and **no migration** — the `vector(768)` column + the
`HNSW vector_cosine_ops` index from migration 0003 are unchanged. The accepted trade-off is
that **CI and the RAGAS evals deliberately stay on the `StubEmbedder`** (no key in CI), so
real semantic vectors are exercised only at runtime / in the live-key smoke, not the PR gate.

### As-built model (live-smoke verified, 2026-06-15)

A throwaway live-key smoke against the real provider settled the model choice empirically
(mirroring the Day-15 chat-model quota discovery):

- **`gemini-embedding-001` SERVES on the free tier** at `output_dimensionality=768` (MRL
  truncation). Cosine sanity passed: a relevant catalog snippet (hiking boots) scored
  **0.75** against a boots query vs **0.48** for an unrelated snippet (t-shirt).
- **`text-embedding-004` is RETIRED — 404** on `v1beta` `embedContent` (the same fate as
  `gemini-1.5-flash` on the chat side). So the "natively-768 fallback" named in the brief
  is **not available**; we ship `gemini-embedding-001` with MRL truncation instead.

So the shipped model is **`gemini-embedding-001`, MRL-truncated to 768** — not the
`text-embedding-004` fallback (which no longer exists for this account).

### Normalization

MRL truncation below the native dimension **un-normalizes** the vector (the live smoke
confirmed raw ‖v‖ ≈ 0.59 at 768-d). `GeminiEmbedder` therefore **L2-normalizes every output
AFTER truncation**, so cosine == dot and the `<=>` HNSW `vector_cosine_ops` index is exact.

### Task types (asymmetric retrieval — the Protocol seam)

Gemini distinguishes `RETRIEVAL_DOCUMENT` (the stored side) from `RETRIEVAL_QUERY` (the
user's query); using the right type per side improves recall. The `Embedder` Protocol's
`embed_text` / `embed_batch` are the **document** path (used by
`refresh_product_embedding` + policy chunking). A separate **`embed_query`** method is the
**query** path (for the future `SemanticRetriever`). `embed_query` has a default that
delegates to `embed_text`, so the `StubEmbedder` stays a no-op, key-free default; only
`GeminiEmbedder` overrides it to switch the task type. This adds the query/doc distinction
without breaking the Protocol or the stub.

## Runtime activation

1. Put a live `GEMINI_API_KEY` in the gitignored repo-root `.env`.
2. Set `EMBED_PROVIDER=gemini` (one line — `EMBED_MODEL=gemini-embedding-001` is the
   default; `EMBED_DIM=768` is unchanged).
3. Re-seed: `refresh_product_embedding` already routes through `get_embedder()`, so
   re-seeding re-embeds the catalog (and policy docs via `upsert_embedding`) with real
   Gemini vectors, replacing the `seed-stub` rows. **No committed seed artifact holds real
   Gemini vectors** — re-embedding is a runtime act.

No migration, no `EMBED_DIM` change, no call-site change.

## Consequences

- The swap was isolated to `app/services/embeddings.py` (register `GeminiEmbedder` in
  `_PROVIDERS`) + one config knob (`EMBED_MODEL`) + `.env.example` — exactly the
  one-line-swap promise of ADR-0026.
- **CI/evals stay on the stub** (default `EMBED_PROVIDER=stub`); the 246-test suite is
  unaffected and key-free. The provider's behavior (768-length, L2-normalized, query-vs-doc
  task routing) is tested against a **mocked** Gemini client — no live call in the suite.
- `EMBED_DIM` is now load-bearing at 768 across three places: the `vector(768)` column, the
  HNSW index, and `GeminiEmbedder`'s MRL truncation. Changing it requires re-running the
  embeddings migration.
- **Deferred:** flipping `_ACTIVE_MODE` → `SearchMode.hybrid` in
  `app/services/search.py` (wiring `SemanticRetriever`/`HybridRetriever` onto this provider)
  is **US-E5-05 (Day 16)** — a deliberate one-line act, untouched here.

## Supporting analysis

Full option comparison (BGE-small vs hosted Gemini, dimensionality / MRL, normalization,
prompt-prefix correctness, adoption sequence): `docs/data/embedding-recommendation.md`.
</content>
