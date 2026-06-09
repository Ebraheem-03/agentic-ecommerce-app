# ADR-0009: Use pgvector/pgvector:pg16 with an init-script extension enable

- **Status:** Accepted
- **Date:** 2026-06-09

## Context
The app needs Postgres + the `vector` extension locally. Options were (a) a plain
`postgres` image plus a custom build that installs pgvector, or (b) the official
`pgvector/pgvector` image that ships the extension preinstalled. The extension also has to
be `CREATE EXTENSION`-ed inside the target database before any embedding column can exist.

## Decision
Use `pgvector/pgvector:pg16` for the `db` service. Enable the extension via
`infra/db/init/01-extensions.sql`, mounted read-only into
`/docker-entrypoint-initdb.d`, which Postgres runs once on a fresh data directory.

## Consequences
No custom DB image to build or maintain; pg16 + pgvector is a known-good pairing.
The init script only runs on an empty data dir — recreating the extension on an existing
volume requires `docker compose down -v` (or a migration), which Sable's Alembic work will
own going forward. Verified live: `SELECT extname FROM pg_extension` returns `vector` 0.8.2.
