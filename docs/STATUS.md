# STATUS — single source of truth

> Atlas updates this at the start and end of every session. Keep it short.

## ▶ Next session — START HERE
You are **Atlas**, the orchestrator (full brief: `.claude/agents/atlas.md`). It's **Week 1 · Day 3 (2026-06-11) — Design system & key screens**.
1. Read **only** this file + the **2026-06-11** block of `docs/plan/week-1.md`. Don't re-read earlier days or the whole repo.
2. Working branch stays **`integration/design`**. Do features on `feature/design-system-*` → `integration/design`.
3. Delegate: **US-E2-04 → Nova/Iris** (design tokens → Tailwind theme / CSS vars), **US-E2-05 → Nova** (hi-fi screens), **US-QA-D03 → Juno/Iris** (UI E2E spec skeleton + stable test IDs). US-E2-04/05 are `[REVIEW]`; US-QA-D03 is `[AFK]`.
4. Day-2 brand is **locked**: name **Hearth**, logo **Keystone**, palette **Clay `#B5512F` / Ember `#E08A3C`**, type **Fraunces + Outfit**. Tokens come straight from `docs/brand/palette-and-type.md` (it has an Iris hand-off block).
5. **Rendering brand artifacts:** there is no system SVG rasterizer — render SVG/HTML previews via the installed **Playwright/Chromium** (`e2e/`); headed window = `chromium.launch({headless:false})`. Don't `pkill -f <script>.js` from a shell whose own argv contains that name (it self-kills).
6. Memory auto-loads via `MEMORY.md`: keep CI green **by code** (GitGuardian scans full PR history); push branches + open real PRs.

**Phase:** Week 1 · Day 2 (2026-06-10) — ✅ COMPLETE. Day 3 not started.
**Current branch:** `integration/design`
**Last updated:** 2026-06-10 (end of Day 2)

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
- _nothing mid-flight_ — Day 2 closed. PR #1 stays open until Day-7 integration.

## ⛔ Blocked
- _nothing_

## 🙋 Needs your decision
- **Day 3 ([REVIEW] x2):** approve design tokens (US-E2-04) · approve hi-fi screens (US-E2-05).
- **Week 4 (deploy):** free-tier keys — Vercel, Render/Fly, Supabase/Neon, Groq/Gemini.

## ⏭️ Next up
- Day 3 stories (above) → tokens become real Tailwind/CSS theme; hi-fi screens for home, search, product, cart, checkout, order status, seller dashboard.
