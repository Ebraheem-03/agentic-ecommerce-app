# ADR-0018: UUIDv7 ids + configurable pgvector dimension/index

- **Status:** Accepted
- **Date:** 2026-06-12
- **Story:** US-E3-02 (schema + Alembic migrations + pgvector)
- **Author:** Sable (Database)

## Context

The approved ERD (`docs/data/erd.md`, §3) calls for UUIDv7 primary keys and a
single polymorphic, chunked pgvector `embeddings` table whose vector dimension is
**not** hardcoded (Echo owns the runtime embedding model). Two non-obvious
implementation choices had to be made when turning that into migrations on the
`pgvector/pgvector:pg16` image.

## Decision

### 1. UUIDv7 via an in-DB SQL function (no native uuidv7, no extra extension)

Base Postgres 16 has **no native `uuidv7()`** (that lands in PG18). Rather than
add the `uuid-ossp` extension (gives v1/v4, not v7) or force every insert to
supply an id, migration `0002` installs a small `uuid_generate_v7()` plpgsql
function built on core `gen_random_uuid()` (pgcrypto, in PG16 core): it overlays a
48-bit millisecond timestamp and sets the version/variant bits. This is the
server-side column `DEFAULT` on every table.

- **Why v7:** time-ordered → index locality close to bigint, while staying
  non-enumerable in URLs/APIs (ties to `J-SUP-01` "no fabrication" + privacy).
- **App may still supply ids:** the column default only covers seeds/manual
  inserts. The app/ORM (US-E3-04) can generate its own v7 ids; both paths produce
  RFC-9562 v7 values. Verified: the default yields `...-7xxx-...` (version nibble 7).
- **Fallback noted:** if we later move to PG18 or a managed PG that exposes native
  `uuidv7()`, we can swap the function body without touching column definitions.

### 2. Embedding dimension + index are config-driven, isolated in their own migration

The `embeddings.embedding` column is `vector(EMBED_DIM)` where `EMBED_DIM` comes
from `app.core.config.settings` (env, **default 768** = Gemini
`text-embedding-004`). The ANN index is **HNSW with `vector_cosine_ops`**
(pgvector 0.8.x in this image ships HNSW; fall back to IVFFlat only if a future
image lacks it).

The embeddings table lives in its **own migration (`0003`)**, separate from the
core schema, so re-sizing to a different model is exactly one step:
`alembic downgrade 0002_core_schema` → set `EMBED_DIM` → `alembic upgrade head`.

- **ECHO COORDINATION POINT:** 768 is a default that lets a fresh DB migrate
  today. Echo confirms the final model/dimension; if it differs, set `EMBED_DIM`
  and re-run the embeddings migration. Nothing else in the schema depends on the
  dimension.

## Consequences

- Migrations apply cleanly on a fresh `pgvector/pgvector:pg16` DB with no
  extension beyond core pgcrypto + the already-enabled `vector`.
- Full round-trip verified: `upgrade head` → `downgrade base` → `upgrade head`
  (21 tables, 14 enums, the uuidv7 function, and the HNSW index all create/drop
  cleanly). This de-risks US-QA-D04.
- Changing the embedding model is a one-migration operation, not a schema rewrite.
- The 768 default is a placeholder pending Echo's confirmation — flagged to Atlas
  as the single open coordination item from this story.
