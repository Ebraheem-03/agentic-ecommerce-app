# STATUS — single source of truth

> Atlas updates this at the start and end of every session. Keep it short.

## ▶ Next session — START HERE
You are **Atlas**, the orchestrator (full brief: `.claude/agents/atlas.md`). It's **Week 1 · Day 4 (2026-06-12) — Data model design**.
1. Read **only** this file + the **2026-06-12** block of `docs/plan/week-1.md`. Don't re-read earlier days or the whole repo.
2. **New working branch: `integration/data`** (off `integration/design`). Features on `feature/db-schema-*` → `integration/data`.
3. Delegate: **US-E3-01 → Sable** (ERD: users, products, variants, inventory, carts, orders, order_items, returns, policies, embeddings) `[REVIEW]`; **US-E3-02 → Sable** (Postgres schema + Alembic migrations + pgvector) `[AFK]`; **US-QA-D04 → Juno/Sable** (migrate fresh DB, rollback check, seed reset contract) `[AFK]`.
4. Carry-forward from Day 3: token layer is live (`web/src/app/globals.css`, Tailwind v4, ADR-0015); the `data-testid` registry (`docs/qa/test-ids.md` + `e2e/tests/_selectors.ts`) and 17 `J-*` fixme specs are the UI contract; 7 hi-fi mockups in `docs/brand/preview/screens/` are Iris's build reference (token-truthful, carry the testids).
5. **Rendering artifacts:** no system SVG rasterizer — render via installed **Playwright/Chromium** (`e2e/`); headed = `chromium.launch({headless:false})`. **Static mocks open via `file://…/screens/<x>.html`; the Next app needs `NODE_OPTIONS="--dns-result-order=ipv4first --no-network-family-autoselection"` for `next/font` fetch in this sandbox** (ADR-0015). Don't `pkill -f <script>.js` from a shell whose own argv contains that name.
6. **Git hygiene:** `git add -A` will sweep `.claude/skills/` + `.claude/worktrees/` as embedded repos — they're now gitignored, but stage explicit paths. Memory: keep CI green **by code** (GitGuardian scans full history); push branches + open real PRs.

**Phase:** Week 1 · Day 3 (2026-06-11) — ✅ COMPLETE. Day 4 not started.
**Current branch:** `integration/design` (push done; PR to `dev` held for Day-7 W1 integration review)
**Last updated:** 2026-06-11 (end of Day 3)

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
- **Day 4 ([REVIEW] x1):** approve the ERD (US-E3-01) before migrations are written.
- **Week 4 (deploy):** free-tier keys — Vercel, Render/Fly, Supabase/Neon, Groq/Gemini.

## ⏭️ Next up
- **Day 4 — Data model:** ERD (users, products, variants, inventory, carts, orders, order_items, returns, policies, embeddings) → Postgres schema + Alembic migrations + pgvector; QA migration/rollback/seed-reset contract. New branch `integration/data`.
