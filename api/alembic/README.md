# Alembic migrations (Hearth backend)

Hand-authored initial schema (US-E3-02). The DB URL is read from the
`DATABASE_URL` environment variable by `env.py` — never hardcoded.

## Run

```bash
# from api/, with deps installed and DATABASE_URL exported
export DATABASE_URL="postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME"
alembic upgrade head        # apply all migrations to a fresh DB
alembic downgrade base      # tear everything back down
alembic current             # show the applied revision
```

The first migration runs `CREATE EXTENSION IF NOT EXISTS vector;` so the schema
applies on a clean database even if the init script never ran.

## Embedding dimension

The `embeddings.embedding` column + its HNSW index are sized from `EMBED_DIM`
(env, default 768 = Gemini text-embedding-004). **Echo owns the final pick.** To
change it: set `EMBED_DIM`, then `alembic downgrade <embeddings-rev>-1` and
`alembic upgrade head` to recreate the column/index at the new dimension.
See `docs/decisions/0018-uuidv7-and-pgvector-dim.md`.
