# DB Migration Test Plan (US-QA-D04)

> Status: **active** · Owner: Juno (QA & Integration) · Day 4 (2026-06-12)
> Turns Sable's one-off manual `upgrade → downgrade → upgrade` proof (US-E3-02)
> into a repeatable, CI-runnable contract. Source of truth for the schema is
> `docs/data/erd.md` (APPROVED 2026-06-12); the three Alembic migrations live in
> `api/alembic/versions/`. Harness decision: `docs/decisions/0019-*.md`.

## What this gate guarantees

Anyone (and CI) can prove, against a real pgvector Postgres, that the schema:

1. **Clean create** — applies onto an empty DB to exactly the expected object set.
2. **Rollback** — reverses cleanly to base, and the up→down→up round-trip is idempotent.
3. **Repeatable reset** — a single guarded command drops+recreates a clean dev DB and
   re-migrates (the hook US-E3-03 seed plugs into).

Object expectations are asserted **by name**, not by count alone, so a wrong-but-
same-count schema cannot pass.

## Artifacts

| Path | Role |
|---|---|
| `api/tests/db/test_migrations.py` | pytest contract — scenarios 1 & 2, catalog assertions |
| `api/tests/db/conftest.py` | throwaway-DB fixture (CREATE/DROP DATABASE per test) |
| `api/scripts/db_reset.sh` | scenario 3 — guarded local reset + seed hook |
| this file | the plan + how to run |

## Expected object inventory (head)

- **21 app tables** (excl. `alembic_version`): 20 from `0002_core_schema` + `embeddings` from `0003`.
  `users, sessions, addresses, stores, products, reviews, variants, product_images,
  inventory, carts, cart_items, orders, order_items, payments, returns, return_items,
  policies, conversations, messages, agent_actions, embeddings`.
- **14 native enums** (`0001`): `user_role, store_status, product_status, cart_status,
  order_status, fulfil_status, payment_status, return_status, return_reason, policy_kind,
  conversation_surface, message_role, agent_outcome, embedding_source`.
- **pgvector** extension present; `embeddings.embedding` is `vector(EMBED_DIM)` (default 768).
- **`uuid_generate_v7()`** function installed (UUIDv7 server-side default — ADR-0018).
- **HNSW cosine index** `ix_embeddings_embedding_hnsw` on `embeddings.embedding`
  (asserted to be access method `hnsw`, not a renamed btree).
- Key constraints asserted: partial-unique `uq_carts_one_open_per_user` (one open cart
  per user), `ck_reviews_rating_range` (rating 1..5), `inventory.variant_id` UNIQUE.

## The three scenarios

### 1. Clean create — `test_clean_create`
Empty throwaway DB → `alembic upgrade head` → assert the full inventory above. A
pre-flight assert confirms the DB is genuinely empty before migrating, so the test
can't be fooled by a dirty DB.

### 2. Rollback + idempotent round-trip — `test_rollback_to_base_then_roundtrip`
`upgrade head` → `downgrade base`, then assert: **0 app tables, 0 enums,
`uuid_generate_v7()` gone**, only `alembic_version` remains and it pins **no** revision.
Then `upgrade head` again returns the full inventory at revision `0003_embeddings`.

> **Documented exception:** `0001`'s downgrade intentionally **leaves the `vector`
> extension in place** — dropping an extension that `infra/db/init/01-extensions.sql`
> also manages is surprising and can break sibling objects. The test asserts the
> extension is still present after `downgrade base` so that a future "drop it too"
> change is a conscious, reviewed decision rather than a silent drift. This is the
> one object that does **not** disappear on full rollback, and it is by design.

### 3. Repeatable local reset — `api/scripts/db_reset.sh`
Drops + recreates the target DB and re-applies migrations to `head`. **Idempotent**
(safe to run repeatedly) and **guarded**: refuses unless the DB name matches a
dev/test pattern (`dev|test|local` by default), bypassable only with `--force` or a
custom `DB_RESET_ALLOW` pattern. The script ends with a marked **seed hook** where
US-E3-03 plugs in `python -m app.db.seed` — keeping reset (pure schema) and seed
(data) as separate concerns.

## How to run locally

A live pgvector Postgres must be reachable. Either the compose `db` service:

```bash
cp .env.example .env            # set POSTGRES_PASSWORD
docker compose up -d db
```

…or any disposable pgvector container, e.g.:

```bash
docker run -d --name hearth-qa-pg -e POSTGRES_PASSWORD=qa_local_pw \
  -e POSTGRES_DB=hearth_test -p 5499:5432 pgvector/pgvector:pg16
```

Then, from `api/` (deps: `pip install -r requirements-dev.txt`):

```bash
# Migration contract (creates/drops its own throwaway DBs on the target server).
# Prefer TEST_DATABASE_URL so it never touches your dev DATABASE_URL.
export TEST_DATABASE_URL="postgresql+psycopg://postgres:qa_local_pw@localhost:5499/postgres"
export EMBED_DIM=768
pytest tests/db -v

# Guarded reset of a dev-named DB.
DATABASE_URL="postgresql+psycopg://postgres:qa_local_pw@localhost:5499/hearth_dev" \
  EMBED_DIM=768 scripts/db_reset.sh
```

If neither `TEST_DATABASE_URL` nor `DATABASE_URL` is set, the migration tests
**skip** (not fail) — they need a real DB and say so.

## How CI runs it

**Status: documented, not yet wired** (the current `.github/workflows/ci.yml` `test`
job is still a green placeholder; replacing it is part of the Day-7 W1 integration so
this story does not destabilize the shared gate). When wired, the `test` (api) job
gains a Postgres service and runs the suite:

```yaml
test-api:
  runs-on: ubuntu-latest
  services:
    db:
      image: pgvector/pgvector:pg16
      env:
        POSTGRES_PASSWORD: ci_pw
        POSTGRES_DB: postgres
      ports: ["5432:5432"]
      options: >-
        --health-cmd "pg_isready -U postgres" --health-interval 5s
        --health-timeout 5s --health-retries 10
  defaults: { run: { working-directory: api } }
  env:
    TEST_DATABASE_URL: postgresql+psycopg://postgres:ci_pw@localhost:5432/postgres
    EMBED_DIM: "768"
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: "3.12" }
    - run: pip install -r requirements-dev.txt
    - run: pytest tests -v
```

`ci_pw` is a throwaway CI value, not a secret. No real credentials enter CI; the
target DB is ephemeral and dropped with the runner.

## Seed-reset contract (for US-E3-03)

The seed story satisfies this contract by plugging into the marked hook in
`db_reset.sh` (a `python -m app.db.seed` invocation against the freshly migrated DB).
The reset itself stays pure schema, so seed can be re-run or skipped independently,
and the migration tests never depend on seed data.
