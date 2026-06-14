# ADR-0026 — Pluggable embedding provider seam + refresh-on-change

- Status: Accepted
- Date: 2026-06-18
- Owner: Sable (Database) — with Echo's AI-layer concerns baked in
- Story: US-E4-08 (embedding generation on product change)

## Context

US-E3-03 shipped a single deterministic `embed_text` stub inside the seed
(`app/db/seed/embeddings.py`, `model='seed-stub'`, length `settings.embed_dim`) so the
`embeddings` table could be populated before a real model existed (ADR-0020). Two things
now need formalizing:

1. **The real embedding model is still an open human `[DECISION]`**, tied to the Week-4
   free-tier Groq/Gemini key. We must NOT hardcode a provider today, but the swap to a
   real model must be cheap and isolated to one place that Echo owns.
2. **Embeddings must stay fresh when product text/attributes change.** Acceptance
   criterion: *"embeddings refresh on update."* Seller write endpoints are still stubs,
   so the refresh has to land as a reusable service the seed uses now and write handlers
   call later — not bolted onto a specific endpoint.

Keyword search is the live retrieval path (Decision-4); pgvector retrieval drops in
behind the same row shape later. So the embeddings only need to be kept correct and
fresh — semantic quality of the stub is irrelevant until a real model lands.

## Decisions

1. **A provider seam in `app/services/embeddings.py`, not in the seed.** Define an
   `Embedder` Protocol — `model` (the tag written to `embeddings.model`),
   `embed_text(text) -> list[float]`, `embed_batch(texts)`. Ship `StubEmbedder` as the
   default: deterministic, content-derived (SHA-256 stream), `model='seed-stub'`, length
   == `settings.embed_dim`. Same text ⇒ same vector (idempotent seed); changed text ⇒
   changed vector (proves refresh-on-update).

2. **Provider selected by config — Echo's swap is one line.** `get_embedder()` resolves
   `settings.embed_provider` (new `EMBED_PROVIDER` env, default `"stub"`) against a
   `_PROVIDERS` registry. To go live, Echo registers a class (e.g.
   `_PROVIDERS["gemini"] = GeminiEmbedder`) and sets `EMBED_PROVIDER=gemini`. No call
   site changes; an unknown provider raises rather than silently falling back to the
   stub. The factory constructs lazily so a key-/network-dependent provider is only built
   when selected.

3. **Refresh is a reusable service, not an endpoint concern.**
   `refresh_product_embedding(session, product_id)` rebuilds the embeddable document
   from the *persisted* product via `build_product_document` (title, description,
   category, sorted attributes, active-variant SKUs + options — stable ordering so the
   document is content-only) and UPSERTs the `(source_type='product', source_id, 0)`
   row. The seed calls it; future seller create/update handlers call it after committing
   a product change. Policies reuse the lower-level `upsert_embedding`.

4. **`EMBED_DIM` stays 768; migration 0003 untouched.** The dimension is still
   env-driven and read from `settings.embed_dim` everywhere (stub length, ORM column,
   tests). A real model with a different dimension is a separate, deliberate down/up on
   migration 0003 — out of scope here.

5. **Seed stub module becomes a back-compat shim.** `app/db/seed/embeddings.py` now
   re-exports `SEED_STUB_MODEL` and `embed_text` (delegating to `StubEmbedder`) so any
   existing import keeps working, but there is now exactly ONE provider seam.

## Consequences

- Echo's swap-in is isolated to `app/services/embeddings.py` (register a provider) +
  one env var; nothing in the seed or write handlers changes.
- Every embedding (seed today, write-handler tomorrow) flows through the same provider,
  so the `model` tag is consistent and stub rows remain bulk-findable
  (`WHERE model='seed-stub'`) for re-embedding when the real model lands.
- The product document definition lives in one function, so the stored vector always
  matches the live product fields — and changing any of those fields + calling refresh
  deterministically changes the vector.
- Trade-off: `build_product_document` defines the searchable surface of a product. If
  Echo wants different chunking (e.g. per-variant chunks) for real RAG, that is a change
  to this one function + the `chunk_index` usage — documented here so it isn't
  surprising. Supersedes the embedding portion of ADR-0020; idempotency strategy there
  still holds.
