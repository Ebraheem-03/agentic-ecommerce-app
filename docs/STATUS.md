# STATUS — single source of truth

> Atlas updates this at the start and end of every session. Keep it short.

## ▶ Next session — START HERE
You are **Atlas**, the orchestrator (full brief: `.claude/agents/atlas.md`). It's **Week 1 · Day 6 (2026-06-14) — API contracts & E2E fixture design**.
1. Read **only** this file + the **2026-06-14** block of `docs/plan/week-1.md`. Don't re-read earlier days or the whole repo.
2. **New integration branch for Day 6: `integration/backend`** (cut from `integration/data` so it carries the schema/models/seed). Features on `feature/<module>-<slug>` → `integration/backend`.
3. Delegate: **US-E4-00 → Orion** (API contract inventory — endpoints, Pydantic v2 request/response models, Scalar docs) `[REVIEW]` — stop and bring the contract to the human before locking; **US-QA-D06 → Juno** (E2E fixture plan — how seeded data + factories back the J-* journeys) `[AFK]`.
4. Carry-forward from Day 5 (all on `integration/data`): **21-table SQLAlchemy 2.0 ORM** on shared `Base` (`api/app/db/models/`, parity-proven no-drift vs migrations) + thin DA layer (`api/app/db/session.py`); **idempotent seed** `python -m app.db.seed` (wired into `db_reset.sh`, `SEED=0` opt-out) — 12 users/5 stores/10 products/15 variants/inventory/12 reviews/7 policies/17 embeddings; **golden eval set v0** `docs/qa/eval/golden-v0.jsonl` (25 Q&A, machine-checkable seed `source_docs`, 4 refusals) + DB-backed validator. ADR-0020. Orion's contracts map to these ORM models; Juno's D06 fixtures build on the seed + `migration_db` throwaway-DB fixture.
5. **Still Echo's (Week-2, not blocking):** `EMBED_DIM=768` placeholder + the single `embed_text` seed stub (`model='seed-stub'`) → swap for the real model + dim, re-run `0003` migration; wire the RAGAS runner that consumes `golden-v0.jsonl` (faithfulness ≥0.90 gate per QA matrix). Keep everything embedding-dim-agnostic — never hardcode 768.
6. **DB ops in this sandbox:** `docker compose up -d db` = `pgvector/pgvector:pg16`; **host 5432 is occupied by a stray `local-postgres`** — run throwaway DBs on an alt host port (agents used 5433/55444). `DATABASE_URL`/`TEST_DATABASE_URL` env-driven, no creds committed (GitGuardian scans full history). Backend deps live in `api/requirements*.txt`; tooling needs a venv (`python -m venv api/.venv`, gitignored) — `ruff`/`mypy`/`pytest` aren't on the base PATH.
7. **Git hygiene:** stage explicit paths (`git add -A` sweeps gitignored `.claude/skills/`+`worktrees/` and `api/.venv`). Integration branches are **not pushed** — held for the **Day-7 (2026-06-15) W1 integration PR** (`foundations|design|data|backend` → `dev`). Keep CI green **by code**.

**Phase:** Week 1 · Day 5 (2026-06-13) — ✅ COMPLETE. Day 6 not started.
**Current branch:** `integration/data` (Day-5 ORM + seed + eval set committed @ `b456a16`; not pushed — held for Day-7 W1 integration review)
**Last updated:** 2026-06-13 (end of Day 5)

## ✅ Done — Day 5 (Seed, data-access & RAGAS data baseline — all 3 stories integrated)
- **US-E3-04** SQLAlchemy models / DA layer `[AFK]` — Sable. SQLAlchemy 2.0 typed ORM (`Mapped`/`mapped_column`) for all **21 tables** on the shared `Base`, split by domain under `api/app/db/models/`. Native PG enums referenced by name (`create_type=False`, labels mirrored from 0001); server defaults mirrored (uuidv7/now/jsonb/bools); partial-unique cart + email-live indexes; `embeddings.embedding = Vector(settings.embed_dim)` (never hardcoded) + HNSW. Thin DA layer `app/db/session.py` (engine + `sessionmaker` + `session_scope`). **Parity-proven vs a real migrated DB**: `test_no_metadata_diff` (Alembic `compare_metadata` → no drift; inline-UNIQUE vs `uq_*` name-only renames filtered), per-table column parity, core round-trip (user→store→product→variant→inventory + embedding at embed_dim). FF-merged `feature/data-access-models` → `9337dcc`.
- **US-E3-03** Seed: catalog/users/policies `[AFK]` — Sable. `python -m app.db.seed` (Hearth maker marketplace) via the ORM: 12 users (all 4 roles), 5 stores, 10 products, 15 variants (real SKUs/price_minor/options), 15 inventory (low-stock + restock_eta spread), images, 12 reviews (1–5 CHECK; **rating rollups recomputed**), **7 policies** (platform returns/shipping/payments/platform + per-store care/returns — genuine quotable RAG prose), 17 embeddings. **Idempotent** (upserts on natural keys); wired into `db_reset.sh` SEED hook (`SEED=0` opt-out). Embeddings via a **single Echo-replaceable `embed_text` stub** (`model='seed-stub'`, length=`settings.embed_dim`). ADR-0020. FF-merged `feature/data-access-seed` → `e4314e4`.
- **US-QA-D05** Golden eval dataset v0 `[AFK]` — Juno (Echo/Sable concerns baked in). **25 buyer/support Q&A** in `docs/qa/eval/golden-v0.jsonl` (JSONL, RAGAS/HF-native): each has `question`, grounded `expected_answer`, machine-checkable `source_docs` (product slug / variant sku / policy `kind@store|platform`), and `tags` (persona/category/difficulty/`expects_refusal`). Spread: buyer 18 / support 7; **4 refusal items** (faithfulness = don't fabricate); embedding-agnostic. Validator `api/tests/qa/test_golden_eval.py`: static well-formedness + **DB-backed seed-resolve** (reuses Sable's `migration_db` fixture → every source_doc resolves to a real row = anti-drift). README maps records → RAGAS metrics + Echo's Week-2 runner work. FF-merged `feature/qa-golden-eval` → `b456a16`.
- **Atlas integration check:** combined `integration/data` gate green **by code** on `pgvector/pgvector:pg16` — `ruff` clean, `mypy --strict` clean (22 files), **pytest 16 passed** (incl. DB-backed seed-resolve + migration contract, no skips).

## ✅ Done — Day 4 (Data model — ERD approved + schema/migrations)
- **US-E3-01** ERD `[REVIEW ✓]` — human-approved with rulings (added `reviews` + minimal `payments`; kept sessions/conversations/messages/agent_actions; single multi-store order with per-item snapshot; `EMBED_DIM`-driven vector dim). `docs/data/erd.md` flipped to APPROVED; §6/§7 resolved inline.
- **US-E3-02** Postgres schema + Alembic + pgvector `[AFK]` — Alembic initialized in `api/` (env-driven `DATABASE_URL`, no creds committed). 3 migrations: 0001 pgvector ext + 14 native enums; 0002 core schema (20 tables, FKs, CHECKs, partial-unique one-open-cart, UNIQUEs on email-live/slug/sku/order_number/inventory.variant_id, UUIDv7 fn+defaults); 0003 embeddings `vector(EMBED_DIM)` + HNSW cosine. **Proven on a fresh DB: `upgrade head` → `downgrade base` → `upgrade head` all clean** (21 tables/14 enums create+drop; uuidv7 nibble=7; dup-open-cart + review-rating CHECK enforced). ruff + mypy(strict) green. ADR-0018. Committed `feature/db-schema-migrations` → FF `integration/data`.
- **US-QA-D04** Migration contract `[AFK]` — turned Sable's one-off proof into a repeatable, CI-runnable gate. pytest `api/tests/db/` (per-test throwaway CREATE/DROP DATABASE, asserts **by name**): clean-create → 21 app tables + 14 enums + pgvector + `uuid_generate_v7()` + HNSW index (access method verified) + one-open-cart partial-unique + reviews CHECK + inventory UNIQUE; rollback → 0 tables/0 enums/fn gone/empty `alembic_version`, then idempotent `upgrade head` back to `0003_embeddings`. Guarded `api/scripts/db_reset.sh` (refuses non-dev DB names, idempotent, seed-hook for US-E3-03). **Proven on `pgvector/pgvector:pg16`: pytest 3 passed; reset guard+reset+idempotent re-run all ✓; ruff + mypy(strict) green.** Documented exception: `0001` downgrade intentionally leaves the `vector` extension (asserted, not a bug). CI = Postgres-service `test-api` job **documented in the plan, wiring deferred to Day-7** so the shared gate stays green. ADR-0019. Committed to `integration/data`.
- **Echo coordination:** `EMBED_DIM` defaults to **768** (Gemini text-embedding-004) so migrations apply today; Echo confirms the final embedding model → set `EMBED_DIM` + re-run the embeddings migration (one step). Not a blocker.

## ✅ Done — Day 3 (Design system & key screens — all 3 stories integrated)
- **US-E2-04** Design tokens → code `[REVIEW ✓]` — **Tailwind v4** (CSS-first, no config), every `palette-and-type.md` token as CSS vars on `:root`+`[data-theme=dark]`, `@theme inline` mapping; Fraunces/Outfit via `next/font`; `Button` (ember+ink primary / clay+white brand), `HearthMark` duotone, `/tokens` specimen + theme toggle. Human approved after a dark-mode tint-badge contrast fix (`text-n-900`). ADR-0015. Merged `915ac62`.
- **US-E2-05** Hi-fi screens `[REVIEW ✓]` — 7 token-truthful static HTML screens (home, search, product, cart, checkout, order-status, seller-dashboard) + index board, in `docs/brand/preview/screens/`. Carry the `data-testid` registry → double as Iris's build contract. Agent voice (Ember) is the signature surface; grounded recs + honest refusals + seller merch nudge. Human approved w/ tweaks: **qty steppers** (not dropdowns) + richer photo placeholders. ADR-0017. Merged.
- **US-QA-D03** UI E2E skeleton `[AFK]` — 17 `J-*` `test.fixme` specs (1:1 w/ QA matrix), `data-testid` registry (`docs/qa/test-ids.md` + typed `_selectors.ts`); agent voice = shared `agent-*` namespace. Smoke stays green (2 passed / 36 skipped, no server). ADR-0016. Merged.
- ADR collision fixed (both agents grabbed 0015 → QA renumbered to 0016); `.claude/skills/`+`worktrees/` gitignored.

## ✅ Done — Day 2 (shipped, all 4 [REVIEW] approved by human)
- **US-E2-01** Brand brief — name **Hearth**, positioning, tone, personas (buyer/seller/support/admin), design hand-off. `docs/brand/brand-brief.md`.
- **US-E2-02** Logo — human locked **"Keystone"** (round 1 of 3 rejected → round 2 of 6). Code-native SVG, not Stitch (ADR-0014). Canonical: `docs/brand/assets/hearth-logo-{mark,lockup}.svg`.
- **US-E2-03** Palette + type — **Clay `#B5512F`** primary / **Ember `#E08A3C`** agent-voice accent; **Fraunces** (serif display/wordmark) + **Outfit** (sans UI); warm-neutral ramp, semantic, light+dark, WCAG AA verified. Spec `docs/brand/palette-and-type.md`, specimen `docs/brand/preview/palette-and-type.html`. Lockup wordmark recut to Fraunces (TODO Day-3: outline to paths once font bundled).
- **US-QA-D02** QA matrix v0 — 4 personas, 17 journeys (`J-*` IDs, 1:1 to D03 E2E), 9 WCAG AA checks, 5 RAGAS gates (**faithfulness ≥0.90** per sign-off). `docs/qa/qa-matrix.md`.
- 4 feature branches FF-merged to `integration/design` (commits `d00c447`→`397f6ec`). ADR-0014.

## ✅ Done — Day 1
- Branch tree `main`→`dev`→`integration/foundations`; remote policy = push + real PRs.
- US-E1-01/02/03/04 + US-QA-D01: monorepo, docker-compose (pgvector, live), CI skeleton, Playwright e2e smoke, CONTRIBUTING. ADRs 0009–0013.
- **PR #1** (`integration/foundations` → `dev`): 9/9 green incl. GitGuardian. Held for the Day-7 gate.

## 🔧 In progress
- _nothing mid-flight_ — Day 5 closed. PR #1 (foundations→dev) stays open until Day-7 integration; `integration/design` pushed, its PR to `dev` also held; `integration/data` carries Day-4+Day-5 work, not pushed — held for Day-7 W1 review.

## ⛔ Blocked
- _nothing_

## 🙋 Needs your decision
- **Week 4 (deploy):** free-tier keys — Vercel, Render/Fly, Supabase/Neon, Groq/Gemini.
- _(ERD [REVIEW] resolved Day 4 — approved with rulings.)_

## ⏭️ Next up
- **Day 6 (2026-06-14) — API contracts & E2E fixtures:** API contract inventory `[REVIEW]` (US-E4-00 → Orion — endpoints + Pydantic v2 models + Scalar, **bring to human before locking**) + E2E fixture plan (US-QA-D06 → Juno). Cut `integration/backend` from `integration/data`; features `feature/<module>-<slug>` → `integration/backend`.
- **Day 7 (2026-06-15):** W1 integration dry run + merge `integration/foundations|design|data|backend` → `dev` `[REVIEW]` (US-QA-D07).
