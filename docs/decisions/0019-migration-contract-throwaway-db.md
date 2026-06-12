# ADR-0019: Migration contract uses a per-test throwaway database

- **Status:** Accepted
- **Date:** 2026-06-12
- **Story:** US-QA-D04 (migrate fresh DB, rollback check, seed-reset contract)
- **Author:** Juno (QA & Integration)

## Context

US-QA-D04 turns Sable's one-off manual `upgrade → downgrade → upgrade` proof
(US-E3-02) into a repeatable, CI-runnable contract. The contract must exercise
migrations **destructively** (downgrade to base wipes everything) and assert the
real catalog, without risking any dev/seed data and without being flaky when run
repeatedly or in parallel with other suites.

Two non-obvious harness choices needed recording.

## Decision

### 1. Each migration test creates and drops its **own** throwaway database

`api/tests/db/conftest.py` connects to the `postgres` maintenance DB on the
env-driven target server (`TEST_DATABASE_URL`, falling back to `DATABASE_URL`),
issues `CREATE DATABASE hearth_mig_test_<rand>` in autocommit, hands the test an
Alembic `Config` + a libpq DSN pointed at that DB, and `DROP DATABASE`s it on
teardown (terminating lingering backends first).

- **Why a separate DB, not a transaction/savepoint:** `CREATE EXTENSION`,
  `CREATE TYPE`, and Alembic's own transactional-DDL mean a rollback-based
  isolation is fragile and doesn't reflect how migrations actually run. A real,
  disposable database is the truthful unit and matches what CI / `db_reset.sh` do.
- **Why `TEST_DATABASE_URL` preferred:** lets a runner point destructive tests at a
  disposable server without disturbing the dev `DATABASE_URL`. If neither is set the
  tests **skip** (not fail) — they need a live pgvector Postgres and say so.
- **No credentials committed:** everything derives from the env URL
  (`.env.example`); CI passes a throwaway `CHANGE_ME`, not a secret.

### 2. The fixture reloads `app.core.config` per test

Alembic's `env.py` reads `settings.database_url`, and `settings` is a module-level
singleton frozen at first import. Without intervention, every test after the first
reuses test 1's (already-dropped) DB URL. The fixture sets `DATABASE_URL` in the env
and `importlib.reload(app.core.config)` so each throwaway DB is genuinely targeted.

- **Why not change `env.py`:** that file is Sable's (US-E3-02) and is correct for
  app/CLI use; the reload is a test-harness concern and stays in the test layer.

## Consequences

- The contract is self-contained and parallel-safe: random DB names, no shared
  state, full cleanup. Runs locally against the compose `db` (or any pgvector
  container) and in CI with a Postgres service.
- Assertions are **by name** (table set, enum set, named indexes/constraints, the
  HNSW access method), so a same-count-but-wrong schema cannot pass.
- One **documented exception** is asserted, not flagged as a defect: `0001`'s
  downgrade deliberately leaves the `vector` extension in place after
  `downgrade base` (dropping an extension `infra/db/init` also manages is
  surprising). The test pins this so any future change to drop it is a conscious one.
- CI wiring is **documented in `docs/qa/db-migration-test-plan.md` but not yet
  applied** — the live `test` job stays a green placeholder until the Day-7 W1
  integration, so this story doesn't destabilize the shared gate.
