# ADR-0012: E2E with Playwright in a top-level `e2e/` workspace

- **Status:** Accepted
- **Date:** 2026-06-09

## Context
We need an end-to-end test harness that covers full product journeys —
search → cart → checkout → order → status, plus edge paths (returns + HITL,
merchandising publish) and agent-layer flows. These journeys span the Next.js
web app, the FastAPI service, and the runtime agent layer, so the suite must be
able to drive a browser *and* hit API/agent endpoints from one place.

Day 1 (US-QA-D01) only needs the foundation: an `e2e` command, an env contract,
a smoke that is green **without** any app server, and a CI slot wired into the
aggregate `ci` gate. Real navigation specs land in US-QA-D03.

Options considered:
- **Playwright** — first-class Next.js fit, built-in browser + API request
  fixtures, parallelism, traces, HTML report. Natural choice for the UI E2E
  specs due in US-QA-D03.
- Cypress — solid UI testing but weaker for cross-cutting API + browser flows
  in one spec and heavier for agent/back-end assertions.
- Hand-rolled (node + fetch) — no browser automation; would need replacing.

Placement: a **top-level `e2e/` workspace** vs colocating in `web/`.

## Decision
Use **Playwright**, in a dedicated top-level **`e2e/`** workspace (its own
`package.json`, `playwright.config.ts`, `tsconfig.json`).

- The `e2e` command is `npm run e2e` (run inside `e2e/`); `npm run e2e:smoke`
  runs only `@smoke`-tagged specs.
- Env contract lives in `e2e/.env.example` (`WEB_BASE_URL`, `API_BASE_URL`),
  resolved as: real process env → `e2e/.env` → `e2e/.env.example`. The config
  exports the resolved base URLs so specs and the env-contract guard share one
  source of truth.
- Day-1 smoke (`tests/smoke.spec.ts`) is server-free: a trivial assertion plus
  an env-contract guard. Real navigation specs are `test.fixme` stubs.
- CI gains an `e2e-smoke` job (installs JS deps only, no browser binaries; runs
  the smoke grep) and is added to the `ci` aggregate's `needs:`.

## Consequences
- One suite can orchestrate web + api + agent flows without coupling to the
  frontend package; the web package stays lean.
- The CI gate covers E2E from Day 1 while staying green with no app code and no
  heavy browser download.
- US-QA-D03 follow-ups: `npx playwright install --with-deps`, a `webServer`
  block to boot web + api, and flipping the `fixme` stubs to real specs.
- Slight cost: an extra workspace to maintain and install separately from
  `web/`. Accepted — the cross-layer reach is worth it.
