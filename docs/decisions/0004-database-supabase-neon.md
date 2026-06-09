# ADR-0004: Managed Postgres: Supabase or Neon

- **Status:** Accepted
- **Date:** 2026-06-09

## Context
Need free managed Postgres with pgvector.

## Decision
Use Supabase (also gives auth/storage) or Neon (serverless, branchable). Both support pgvector.

## Consequences
Local dev uses the docker-compose Postgres; dev/prod use the managed instance. Keep migrations the single source of truth across both.
