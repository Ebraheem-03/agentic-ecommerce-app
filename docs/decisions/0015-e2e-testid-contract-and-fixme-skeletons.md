# ADR-0015: E2E test-id contract + fixme-only journey skeletons

- **Status:** Accepted
- **Date:** 2026-06-11

## Context
US-QA-D03 documents the UI E2E spec skeletons and a stable selector registry for the
7 key screens **before** any frontend code exists. Two forces: (1) specs must map 1:1
to the `J-*` journeys in `docs/qa/qa-matrix.md` and reference concrete selectors so
Iris/Nova build against a known contract; (2) the server-free `@smoke` CI job must stay
green — no spec may require a running web/api server yet.

## Decision
1. **Selectors are a published contract.** Canonical `data-testid` values live in
   `docs/qa/test-ids.md` (human-facing) and are mirrored as typed constants in
   `e2e/tests/_selectors.ts` (`TID.<screen>.<element>`). Specs select only via
   `getByTestId(TID...)`, never by text/role, so copy/i18n changes don't break them.
   IDs are `kebab-case`, namespaced by screen (`search-input`, `checkout-place-order`).
   The agent chat surface is its own cross-screen `agent-*` namespace.
2. **Every journey spec is `test.fixme` until the app is up.** One file per `J-*` ID,
   `test.describe('J-XXX: <title>')`. `fixme` (not `skip`) marks them as "expected to run
   later": Playwright discovers and TS-checks them but never executes, so `@smoke` and the
   full run stay green with no server. Activation = add a `webServer` block to
   `playwright.config.ts` and flip `test.fixme` -> `test` per spec.
3. **`_selectors.ts` is a non-spec helper** (filename has no `.spec.`), so `testMatch`
   ignores it while `tsconfig` still type-checks it.

## Consequences
- Easier: frontend can build to a stable selector contract from day one; specs are
  reviewable now; flipping a journey to live is a one-line change once its screen exists.
- Harder/trade-off: `test-ids.md` and `_selectors.ts` must be kept in lockstep — adding a
  spec anchor means editing both in the same PR. A future drift-check (lint) could enforce this.
- The e2e workspace has no `typescript`/`@types/node` dependency yet, so a strict
  `tsc --noEmit` needs them installed transiently. Wiring a real type-check step into the
  e2e package + CI is a follow-up.
