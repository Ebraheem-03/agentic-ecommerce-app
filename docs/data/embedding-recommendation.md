# Embedding Model + Dimensionality — Recommendation

**Status: PROPOSED — pending human decision.** If accepted, this becomes ADR-0032.
Author: Echo (AI/Agents). Scope: a written recommendation only — no config, migration,
or provider changes are made here.

---

## TL;DR

- **Top pick: a self-hosted `BAAI/bge-small-en-v1.5` (BGE-small) running in the API
  container, at `EMBED_DIM = 384`.** It makes semantic search and the RAGAS harness work
  **key-free and offline in CI** — which is a hard constraint for us — while being tiny
  enough (~130 MB, CPU-fast) for the free-tier Dockerized stack.
- **2nd choice: hosted `gemini-embedding-001` at `EMBED_DIM = 768` (MRL-truncated).**
  Stronger raw quality and zero model weights in the image, but it needs a live key, so CI
  would have to stay on the stub — semantic search would *not* exercise real vectors in CI.
- **One-liner:** want *best recall + zero infra* → hosted Gemini; want *semantic search
  that actually runs in CI with no keys* (our stated constraint) → self-hosted BGE-small.

I recommend **BGE-small** because the constraint "CI + the RAGAS eval must run key-free"
is load-bearing for this portfolio: the value we're showcasing is *hybrid retrieval that
works end-to-end*, and a stub-only CI never proves that.

---

## Why this fits THIS use case

Our use case is two consumers of one embedding column:

1. **Semantic product search** over ~10 products / ~15 variants of short English blurbs
   (title/description/category/variant options — see `build_product_document`). The Day-10
   smoke showed keyword recall on natural-language *questions* = 0.000; that's exactly the
   query→document vocabulary-mismatch gap that dense retrieval closes.
2. **RAG grounding** over the same catalog **plus 7 short policy prose docs**
   (returns/shipping/payments/care), feeding the RAGAS faithfulness gate (≥0.90).

Key properties of THIS workload that drive the pick:

- **Short, mostly-English, single-domain text.** No long-document, multilingual, or code
  needs. A small English-tuned model (BGE/E5/GTE-small class) is right-sized; a 3072-dim
  frontier model is overkill and wastes storage/latency on a tiny corpus.
- **Tiny corpus, cosine + HNSW already wired.** Migration 0003 builds
  `vector(EMBED_DIM)` with an HNSW `vector_cosine_ops` index. All the families below are
  trained for cosine/dot on **L2-normalized** vectors, so they slot into our existing index
  with no metric change.
- **Asymmetric retrieval (short query → short doc).** This is the regime BGE/E5 were
  explicitly trained for, and where their query/passage instruction prefixes matter (below).
- **The constraint that decides it: CI + RAGAS must run with NO external keys.** Today they
  use the stub. A stub vector is cosine-meaningless, so *semantic* behavior is untested in
  CI. A self-hosted model is the only way to make semantic/hybrid retrieval and the
  faithfulness gate run on **real** vectors in CI, offline.

---

## Dimensionality (incl. Matryoshka / MRL)

- **BGE-small → 384 dims, full (no truncation).** The model is natively 384-d; that's
  already small. At ~25 catalog+policy rows, 384-d HNSW is trivial on storage and latency,
  and you keep the model's full trained recall. No MRL needed — truncating a 384-d model
  buys nothing here and only risks recall.
- **If you instead go hosted Gemini → MRL-truncate to 768.** `gemini-embedding-001` is
  natively high-dim with **Matryoshka** support (recommended truncation sizes 768 / 1536 /
  3072). For our corpus, **768** is the sweet spot: it matches our *current* `EMBED_DIM`
  default, so the migration footprint is zero, and the storage/speed win over 3072 is real
  while recall loss on short English text is negligible at this scale.
  - **MRL tradeoff in one line:** smaller dim = less storage + faster ANN, slightly lower
    recall; the loss is sub-linear (that's MRL's point), and for a ~25-doc corpus it's
    immaterial. I would *not* go below 768 on the hosted path, and I would *not* go above
    768 (3072 is pure cost for no measurable gain on this corpus).
  - **Normalization caveat:** `gemini-embedding-001` requires **manual L2-normalization**
    when you truncate below its native dimension. (The newer `gemini-embedding-2` auto-
    normalizes truncated dims, but it's newer/less battle-tested; if the human prefers it,
    truncate to 768 and you can skip manual normalization — but treat it as the bleeding
    edge.)

**EMBED_DIM implication:**
- BGE-small (top pick) → **`EMBED_DIM` changes 768 → 384**. This requires re-running
  migration 0003 (the vector column + HNSW index are dimension-typed) and a full re-embed.
- Hosted Gemini @768 (2nd choice) → **`EMBED_DIM` stays 768**, so the column/index are
  unchanged; you only re-embed (stub vectors → real Gemini vectors). This is the *lower-
  footprint* migration, and is a fair reason to favor it if avoiding a schema change matters
  more than key-free CI.

---

## The hosting axis — the real decision

| | **Self-hosted BGE-small (pick)** | **Hosted Gemini (2nd)** |
|---|---|---|
| CI / RAGAS key-free | **Yes** — real vectors, offline | No — CI stays on stub |
| Semantic search proven in CI | **Yes** | No (stub only) |
| Infra in the container | ~130 MB weights + CPU inference | None |
| Runtime cost / quota | Free, local | Free-tier quota + network/latency |
| Raw quality on hard queries | Strong (small-model class) | Higher ceiling |
| `EMBED_DIM` | 384 (migration needed) | 768 (no schema change) |

**My call: self-hosted BGE-small.** Reasoning specific to us:

- The single most important non-negotiable in the brief is "**CI + the RAGAS harness must
  run key-free/offline.**" A hosted embedder *cannot* satisfy that for the semantic path —
  you'd be forced to keep CI on the stub, meaning your hybrid-retrieval and faithfulness
  story is never actually exercised by CI. For a portfolio whose headline is *agentic
  retrieval that works*, that's the wrong tradeoff.
- BGE-small is small enough to bake into the API image (or download once at build) and run
  on CPU for our corpus size without a GPU or a separate service. `docker compose up` stays
  a single-command bring-up.
- It also removes a runtime dependency: no Gemini embedding quota consumed per search, no
  network hop on the hot path, no key needed for the *search* feature at all. (Gemini stays
  the **chat** LLM via `llm_provider` — unaffected.)

**When the 2nd choice wins:** if the human decides they do *not* want any model weights in
the container and are fine with CI proving semantic only via a manual/keyed nightly job
(not the default PR gate), then hosted `gemini-embedding-001 @768` is clean, higher-ceiling,
and needs *no schema change*. That's a legitimate "zero-infra" posture — it just trades away
key-free semantic CI.

**Why BGE-small over E5/GTE/Nomic/Jina-small:** all are competitive in this size class. I
pick BGE-small because it's the most widely-deployed, well-documented English asymmetric
retriever with a clean `sentence-transformers` load path and a simple query-instruction
convention (below). E5-small-v2 is a near-equal alternative (swap-in); GTE-small is fine
too. Nomic/Jina lean toward long-context (8k), which we don't need — their advantage is
wasted on policy paragraphs and product blurbs. No strong reason to pay their larger
footprint here.

---

## Normalization / distance / prompt-prefix correctness (matters for our seam)

These are not cosmetic — getting them wrong silently degrades recall through our
`SemanticRetriever`/`HybridRetriever` seam.

- **Distance:** all recommended models are cosine/dot models. Our HNSW index is
  `vector_cosine_ops` (`<=>`), which is correct as-is. **No index change** for either pick.
- **L2-normalize before storing.** BGE/E5/GTE expect **L2-normalized** vectors; normalize
  in the embedder (`StubEmbedder`'s replacement) so cosine == dot and `<=>` is exact. With
  normalized vectors, cosine distance and dot product agree — the cleanest invariant for the
  HNSW index. For hosted `gemini-embedding-001` truncated to 768, **manually L2-normalize**
  (only the native dim is pre-normalized).
- **Query vs document instruction prefixes (asymmetric models).** This is the
  easy-to-miss correctness item for our two-sided seam:
  - **BGE-small:** prefix the **query** with
    `"Represent this sentence for searching relevant passages: "`; the **document** is
    embedded **as-is** (no prefix). BGE is asymmetric: query-prefix only.
  - (E5 convention, if chosen instead: prefix `"query: "` on queries and `"passage: "` on
    documents.)
  - **Seam implication:** our `Embedder` Protocol currently has one `embed_text`. The real
    provider needs to distinguish **query** embedding (in `SemanticRetriever.retrieve`,
    where we embed the user's `query`) from **document** embedding (in
    `refresh_product_embedding` / policy chunking). Cheapest fix that respects the Protocol:
    have the provider apply the **document** convention in `embed_text`/`embed_batch`
    (so the stored `refresh_product_embedding` path is correct with no signature change),
    and add a small `embed_query(text)` method (or a `is_query: bool` kwarg) used only by
    `SemanticRetriever`. Note this when you wire the provider — it's a Protocol nuance, not a
    config flag. Skipping the query prefix on BGE measurably hurts recall.

---

## Concrete adoption steps in our seam (no code changes now — the sequence)

For the **BGE-small (top pick)** path:

1. **Register the provider.** Add `BGEEmbedder` (a `sentence-transformers` wrapper
   satisfying the `Embedder` Protocol, `model="BAAI/bge-small-en-v1.5"`) to
   `_PROVIDERS` in `api/app/services/embeddings.py`. It must: return `settings.embed_dim`-
   length vectors, L2-normalize, embed documents un-prefixed, and expose a query path that
   applies the BGE query instruction (see seam note above).
2. **Set env.** `EMBED_PROVIDER=bge` and **`EMBED_DIM=384`** (changes the current 768
   default — coordinate with Orion/Sable on `.env.example` + config default).
3. **Re-run migration 0003.** Because `EMBED_DIM` changes (768→384), the vector column and
   HNSW index must be rebuilt: `alembic downgrade 0003_embeddings` (drops `embeddings`) then
   `alembic upgrade head` with `EMBED_DIM=384` in the env so the column is `vector(384)`.
4. **Re-embed.** Run `refresh_product_embedding(session, product_id)` for every product
   (the seed path), and embed the 7 policy docs through the same `upsert_embedding`
   (`source_type='policy'`). Stub rows (`model='seed-stub'`) are trivially found for bulk
   replacement.
5. **Flip retrieval to hybrid.** Implement `SemanticRetriever.retrieve` (cosine `<=>` ANN
   over `embeddings.embedding`) + `HybridRetriever` (RRF fuse keyword+semantic → `rerank()`),
   then set `_ACTIVE_MODE = SearchMode.hybrid` in `api/app/services/search.py`. The response
   contract is unchanged (Decision-4).
6. **Bake the model for offline CI.** Ensure the BGE weights are present in the image / cached
   so CI runs with no network/keys. Then point the RAGAS harness's embedder off the stub so
   faithfulness is measured on real vectors.

For the **hosted Gemini @768 (2nd choice)** path, the sequence is the same **except**:
`EMBED_PROVIDER=gemini`, **`EMBED_DIM` stays 768 → no migration 0003 re-run** (only re-embed),
manual L2-normalize on truncation, and CI/RAGAS stay on the stub (or a keyed nightly job)
since the provider needs a live key.

---

## One-line summary

> **Zero-infra, no schema change:** hosted `gemini-embedding-001 @768` (CI stays stubbed).
> **Best end-to-end story incl. key-free semantic CI:** self-hosted **BGE-small @384** —
> my recommendation.
