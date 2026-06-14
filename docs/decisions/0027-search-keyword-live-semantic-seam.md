# ADR-0027 — Catalog search: keyword retrieval LIVE, semantic/hybrid seam + rerank stub

- Status: Accepted
- Date: 2026-06-18
- Story: US-E4-07 (Day 10)
- Owner: Orion (with Sable index concern)
- Supersedes / relates: contract-v0 Decision-4 (search v0), ADR-0026 (embedding provider seam), ADR-0025 (catalog cursor + inventory)

## Context

contract-v0 **Decision-4** locks search v0 as *keyword-only, semantic-ready*: keyword
retrieval is the live path now; pgvector/semantic retrieval is **deferred to Echo
(Week-4)** and must drop in behind the **same response shape with no contract change**.
The `GET /search` response already exposes a per-result `score` and a retrieval `mode`
discriminator (`SearchMode`: `keyword` | `semantic` | `hybrid`). No embedding dimension
is baked here — Echo owns `EMBED_DIM` (ADR-0018/0026).

## Decision

**1. Keyword retrieval = Postgres full-text search (not ILIKE).**
A STORED generated `tsvector` column `products.search_tsv` (migration **0005**) over the
searchable text, weighted **title `A` > category `B` > description `C`**, with a **GIN**
index `ix_products_search_tsv`. Queries use `websearch_to_tsquery('english', q)` matched
with `@@` and ordered by `ts_rank(search_tsv, query)` — that rank is the per-result
`score`. Chosen over ILIKE because it gives real relevance ranking, weighting, stemming,
and phrase/boolean operators (`"quoted"`, `OR`, `-term`) for free, and the GIN index keeps
it fast as the catalog grows. The generated column stays in sync with the row with no
trigger and no app-side maintenance; it is marked `Computed(persisted=True)` on the ORM so
SQLAlchemy never writes it.

**2. Retriever seam.** A `Retriever` Protocol (`mode`, `retrieve() -> list[ScoredProduct]`)
with a live `KeywordRetriever` and inert-but-present `SemanticRetriever` / `HybridRetriever`
seams. The active retriever is a single module-level reference (`_ACTIVE_MODE`,
`get_retriever()`). The semantic seam documents exactly where Echo embeds the query via
`app.services.embeddings.get_embedder()` (US-E4-08) and runs a cosine ANN search over the
`embeddings` HNSW index; today it raises `NotImplementedError` if selected, so turning it
on is a deliberate act, never a silent default.

**3. `rerank()` = identity passthrough today.** The call site exists in `search_products`
so Echo's cross-encoder/LLM reranker plugs in with zero call-site change.

**4. `mode` surfaces in `meta`.** The `{data, meta}` envelope is preserved; `SearchMeta`
(extends `PageMeta`) carries `mode`, and `SearchEnvelope` pins `meta` to it. Semantic/hybrid
retrieval changes only the `mode` **value**, never the shape.

**5. No ranked cursor in v0.** Relevance ordering has no monotonic keyset, so the shared
`(created_at, id)` cursor does not apply. v0 returns a single ranked page
(`next_cursor = null`, capped at `limit`). `cursor` is accepted for forward-compatibility
but not yet honored; a ranked cursor is deferred with semantic retrieval. Adding it later is
non-breaking (the response shape is unchanged).

## Consequences

- Echo enables semantic/hybrid with **no contract change**: flip `EMBED_PROVIDER` to a real
  model (ADR-0026) + point `_ACTIVE_MODE`/`get_retriever()` at the semantic/hybrid retriever,
  and optionally swap the identity `rerank()` for a real one. Same endpoint, same `{data,
  meta}` envelope, same `SearchResult` — only `meta.mode` and the `score` semantics change.
- Migration **0005** adds the generated column + GIN index; reversible (down drops index then
  column), proven up→down→up clean. `EMBED_DIM`/migration 0003 untouched. The migration test
  head assertion was repointed `0004_email_verified → 0005_product_search` and now asserts the
  FTS column + GIN index exist. The ORM declares the index in `__table_args__` so model↔schema
  parity holds.
- Empty query / over-long query / limit>100 → canonical `422 validation_error`; a query with
  no matches → `200` with empty `data` (not a 404).
