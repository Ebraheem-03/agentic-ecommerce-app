# ADR-0010: Keep docker-compose.yml at the repo root

- **Status:** Accepted
- **Date:** 2026-06-09

## Context
CLAUDE.md §9 requires a single compose file to bring up the full stack, and the story
allowed it to live at the root or under `infra/`. Build contexts point at `./web` and
`./api`; the DB init bind-mount points at `./infra/db/init`.

## Decision
Place `docker-compose.yml` at the repo root. The `.env`/`.env.example` and the documented
`docker compose up` command also live at the root.

## Consequences
`docker compose up` works from a fresh clone with no `cd` or `-f` flag — the lowest-friction
default and what the README quickstart documents. Relative build contexts stay short
(`./web`, `./api`). Deploy-specific compose overrides, if ever needed, can still live under
`infra/` and be layered with `-f`.
