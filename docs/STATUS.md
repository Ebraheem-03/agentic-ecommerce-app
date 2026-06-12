# STATUS — single source of truth

> Atlas updates this at the start and end of every session. Keep it short.

## ▶ Next session — START HERE
You are **Atlas**, the orchestrator (full brief: `.claude/agents/atlas.md`). It's **Week 1 · Day 5 (2026-06-13) — Seed, data-access & RAGAS data baseline**.
1. Read **only** this file + the **2026-06-13** block of `docs/plan/week-1.md`. Don't re-read earlier days or the whole repo.
2. **Stay on branch `integration/data`** (Day-4 schema/migrations live here). Features on `feature/data-access-*` → `integration/data`.
3. Delegate: **US-E3-03 → Sable** (seed data: catalog, users, policies — must satisfy the migration `db_reset.sh` seed-hook + feed pgvector embeddings) `[AFK]`; **US-E3-04 → Sable** (SQLAlchemy models / data-access layer mapping the 21-table schema; unit tests) `[AFK]`; **US-QA-D05 → Juno/Echo/Sable** (golden eval dataset v0 — 25 buyer/support Qs w/ expected answer + source docs + tags, for catalog/policies RAGAS) `[AFK]`.
4. Carry-forward from Day 4: schema is live as 3 Alembic migrations in `api/` (21 tables, 14 enums, pgvector HNSW; ADR-0018). Contract: `api/tests/db/` + guarded `api/scripts/db_reset.sh` (has a marked **seed hook** US-E3-03 plugs into; ADR-0019). **`EMBED_DIM=768` is a placeholder — Echo owns the final embedding model/dim**; US-E3-03 embeddings + US-QA-D05 eval set must not hardcode assumptions that break if it changes. `docs/data/erd.md` is the APPROVED model of record.
5. **DB ops in this sandbox:** Postgres via `docker compose` (`pgvector/pgvector:pg16`); `DATABASE_URL`/`TEST_DATABASE_URL` env-driven (`.env.example`, no creds committed). Migrate with `alembic upgrade head` from `api/`. UUIDs come from in-DB `uuid_generate_v7()`. Don't hardcode creds (GitGuardian scans full history).
6. **Git hygiene:** `git add -A` sweeps `.claude/skills/` + `.claude/worktrees/` (gitignored, but stage explicit paths). Integration branches are **not pushed** — held for the **Day-7 (2026-06-15) W1 integration PR** (`foundations|design|data` → `dev`). Keep CI green **by code**.

**Phase:** Week 1 · Day 4 (2026-06-12) — ✅ COMPLETE. Day 5 not started.
**Current branch:** `integration/data` (Day-4 schema + migration contract committed; not pushed — held for Day-7 W1 integration review)
**Last updated:** 2026-06-12 (end of Day 4)

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
- _nothing mid-flight_ — Day 3 closed. PR #1 (foundations→dev) stays open until Day-7 integration; `integration/design` pushed, its PR to `dev` also held for the Day-7 W1 review.

## ⛔ Blocked
- _nothing_

## 🙋 Needs your decision
- **Week 4 (deploy):** free-tier keys — Vercel, Render/Fly, Supabase/Neon, Groq/Gemini.
- _(ERD [REVIEW] resolved Day 4 — approved with rulings.)_

## ⏭️ Next up
- **Day 5 (2026-06-13) — Seed, data-access & RAGAS baseline:** seed catalog/users/policies (US-E3-03) + SQLAlchemy models / data-access layer (US-E3-04) + golden eval dataset v0, 25 buyer/support Qs (US-QA-D05). Branch `feature/data-access-*` → `integration/data`.
- **Day 6 (2026-06-14):** API contract inventory `[REVIEW]` (US-E4-00) + E2E fixture plan (US-QA-D06) → `integration/backend`.
- **Day 7 (2026-06-15):** W1 integration dry run + merge `integration/foundations|design|data` → `dev` `[REVIEW]` (US-QA-D07).
