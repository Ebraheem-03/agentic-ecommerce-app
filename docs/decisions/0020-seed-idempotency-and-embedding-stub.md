# ADR-0020 — Seed idempotency strategy + Echo-replaceable embedding stub

- Status: Accepted
- Date: 2026-06-13
- Owner: Sable (Database)
- Story: US-E3-03 (seed data)

## Context

The seed (`app.db.seed`, run via `python -m app.db.seed`) must populate a believable
Hearth marketplace AND be safe to re-run — it is wired into `api/scripts/db_reset.sh`
and may run repeatedly in dev/CI. It also has to generate `embeddings` rows before
Echo's real embedding provider exists, without hardcoding a dimension or provider.

## Decisions

1. **Idempotency via natural-key upserts (not truncate-and-reload).** Every entity is
   looked up on a stable natural key before insert: user `email` (live), store `slug`,
   product `slug`, variant `sku`, policy `(store_id, kind, title)`, embedding
   `(source_type, source_id, chunk_index)`. Re-running updates mutable fields in place,
   so counts stay constant and FKs/UUIDv7 ids are preserved across runs. Chosen over a
   wipe-and-reseed so a reseed doesn't invalidate ids other dev data/fixtures may hold.

2. **Derived rollups recomputed in the seed.** `products.rating_avg/rating_count` are
   app-derived (per the ERD). The seed recomputes them from the actual `reviews` rows
   after upserting reviews, so the rollup is correct and re-running is stable.

3. **Single Echo-replaceable embedding function.** `seed/embeddings.py::embed_text` is
   the ONLY place a vector is produced. It returns a deterministic, hash-derived vector
   of length `settings.embed_dim` (read from config — never hardcoded 768) and every row
   is tagged `model = "seed-stub"`. Echo replaces just the body with a real provider call,
   keeping the signature and the length contract. The stub is not semantically meaningful
   — it exists to satisfy `NOT NULL` + the pgvector dimension contract so retrieval
   plumbing can be wired and tested before real embeddings land.

4. **`db_reset.sh` seeds by default, `SEED=0` opts out.** The reset hook runs the seed
   after migrating to head; because the seed is idempotent, this is safe. `SEED=0` keeps
   the script usable as a pure schema reset.

## Consequences

- Reseeding is cheap and non-destructive; CI/dev can reset+seed freely.
- A future `EMBED_DIM` change (one down/up on migration 0003) automatically re-sizes
  seeded vectors on the next reseed — no seed edit needed.
- Echo's swap-in is a one-function change; stub rows are trivially found via
  `model = 'seed-stub'` for bulk re-embedding.
- Trade-off: upsert-on-natural-key means renaming a natural key (e.g. a product slug)
  in `data.py` creates a new row rather than renaming the old one. Acceptable for seed
  content; documented here so it isn't surprising.
