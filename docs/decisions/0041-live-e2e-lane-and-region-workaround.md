# ADR-0041 — The `@live` E2E lane (next-dev, real stack) + the checkout `region` test-side workaround

- **Status:** Accepted
- **Date:** 2026-06-16 (W4D1 / Day 22)
- **Owner:** Juno (QA & Integration)
- **Context ADRs:** ADR-0040 (FE flip-to-live), ADR-0038 (agentic-checkout approval gate),
  ADR-0037 (FE mock SSE + shop clients), ADR-0012 (top-level e2e workspace)

## Context
ADR-0040 flipped the happy-path `/api/*` route handlers to proxy the live FastAPI.
US-E7-01 requires an E2E that proves the happy path against the LIVE full stack
(web → api `:8000` → db) with zero mocks. The existing `@web` browser lane self-boots
`next build && next start` over the ADR-0037 mocks — neither the build nor the mock
posture fits the live proof:

1. The sandbox **blocks the build-time Google-Fonts fetch** (`next/font/google`
   ETIMEDOUT), so `next build` fails offline.
2. The live stack has constraints the mock lane never had: the live Ember planner
   loops (DEFECT-D22-01), live state persists in a real DB (not a clean slate), and
   `next dev` hydrates routes lazily on first hit.

## Decisions
1. **Add a dedicated `@live` lane, switched by `E2E_LIVE=1`** (`npm run e2e:live`).
   In that lane `playwright.config.ts`:
   - boots the web app with **`next dev`** (not `build`) on **port 3200** (isolated
     from the `@web` build on 3100 and a dev server on 3000),
   - injects `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` so the SSR product
     resolver + the proxy handlers hit the real API,
   - runs **one** chromium project (the live DB is shared mutable state — a second
     viewport racing the same buyer's cart/orders is self-defeating),
   - forces `WEB_BASE_URL=:3200` even if `e2e/.env` pins 3100 for `@web`.
   The server-free `@smoke` lane (ADR-0012) and the `@web` lane are untouched.

2. **Non-conversational journey entry.** The spec NEVER touches Ember chat
   (DEFECT-D22-01 loops the live planner). It deep-links the PDP by seeded slug
   (`/product/carryall-card-wallet`). The FE-orchestrated approval gate (ADR-0038)
   calls the order endpoints directly, not the agent runtime, so it runs fine live.

3. **Robust to live (persistent) state.** The spec clears the buyer's cart at the
   start (real `DELETE /cart/items/{id}`), asserts on the line it adds, and never
   asserts the orders-list length — it deep-links the freshly placed order by id.

4. **Hydration-tolerant interactions.** Under `next dev`, client islands hydrate
   lazily; a too-early click submits the login form natively (a GET, no cookie). The
   spec retries interactions (`expect(...).toPass`) until the JS handler's network
   call actually fires / the live cart reflects the add.

5. **`region` handled test-side, app code untouched** (see below).

## DEFECT-D22-02 — checkout `region` (filed to Iris) and why the test patches it
The live `AddressIn` requires `region` (`min_length=1`, `api/app/schemas/common.py`),
but the `CheckoutFlow` form (`web/src/components/checkout/CheckoutFlow.tsx`) has **no
region field** and defaults `region: ""`; `toBackendAddress`
(`web/src/lib/adapters/order.ts`) passes it through verbatim. So a **pure-UI live
checkout 422s** (`string_too_short` on `ship_address.region`) — the happy path cannot
complete through the real form.

Following the established "patch the TEST, not app code" posture (the D20 HITL
data-spine gap set this precedent), the `@live` spec intercepts the outbound
`POST /api/orders` body and fills a region so the live order PLACES end-to-end (the
request still hits `:8000` → DB; a real order row persists). No app code is touched.

**Fix-forward (Iris's):** either add a Region input to the checkout form and drop the
empty default, or default a region in `toBackendAddress` (least-surprise: render the
field, since the backend treats it as required shipping data).

## Consequences
- US-E7-01 passes: `npm run e2e:live` drives login → PDP → cart → gate → two-step
  payment (captured) → confirmation → `/orders` timeline+Paid against `:8000`, and a
  real `HEA-…` order persists in the live DB.
- DEFECT-D22-02 is a known, filed FE gap; the live happy path is green only because
  the spec supplies the region. Once Iris fixes the form, the route-intercept can be
  dropped.
- No CI change: the `@live` lane needs the live stack up, so it stays a local/manual
  lane (like the booted `@web` lane, which is also not in CI). The server-free
  `@smoke` lane remains the CI gate.
