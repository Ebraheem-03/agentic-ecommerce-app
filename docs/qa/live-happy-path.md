# Live happy-path E2E (US-E7-01, the `@live` lane)

The **live-stack** money-path proof: `e2e/tests/live-happy-path.spec.ts` drives the
WHOLE buyer journey against the REAL stack — web (`next dev` + the `/api/*` proxy
handlers + the SSR product resolver) → FastAPI `:8000` → Postgres — with **zero
mocks**. This is the W4D1 flip-to-live deliverable (ADR-0040).

```
log in as ada (real session cookie)
  → reach a PDP the DETERMINISTIC way (direct seeded slug, NOT Ember chat)
  → add to cart  → /cart shows the real line
  → checkout → approval gate restates totals → Approve
  → two-step payment (intent → confirm, captured)
  → order confirmation  → /orders shows the placed+paid order + timeline
```

## Running it

The live FastAPI must be up on `:8000` (root `.env` loaded, seeded DB on `55444`).
From `e2e/`:

```bash
npm run e2e:live
```

`E2E_LIVE=1` makes `playwright.config.ts`:

- self-boot the web app with **`next dev`** (NOT `next build` — the sandbox blocks
  the build-time Google-Fonts fetch) on **port 3200** (so it never collides with
  the `@web` build on 3100 or a dev `next dev` on 3000),
- wire it to the live backend via `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
  (this is what makes the SSR resolver + proxy handlers talk to the real API),
- run **one** chromium project (`live-chromium`) — the live DB is shared mutable
  state, so racing two viewports over the same buyer's cart/orders is self-defeating.

Navigation uses `domcontentloaded` (NOT `networkidle` — the docked Ember SSE
stream hangs `networkidle`).

## Why non-conversational entry (load-bearing)

**DEFECT-D22-01** (deferred to Day 23 / US-E7-05): the live Ember shopping planner
LOOPS — it re-issues the same `search` every step and never replies, falling back
gracefully. So the conversation-first `/search` page can't complete a turn under
the live LLM. The `@live` spec therefore **never touches Ember chat**; it deep-links
the PDP by seeded slug. The checkout approval gate is FE-orchestrated (ADR-0038) and
calls the order endpoints directly (not the agent runtime), so it works fine live.

## Live state is not a clean slate

The buyer's cart + orders persist in the real DB across runs. The spec is robust to
pre-existing state: it **clears the cart at the start** (removing whatever lines are
there via the real `DELETE /cart/items/{id}` proxy), asserts on the line it adds, and
never asserts the orders-LIST length — it deep-links the freshly placed order by its
real id. The placed order number (`HEA-…`) is logged to the run output and attached
as a `live-order-number` test annotation for cross-checking the DB row.

## Hydration under `next dev`

`next dev` compiles + hydrates each route on first hit. Client islands (the login
form's `onSubmit`, the buy-box add-to-cart `onClick`) only fire after hydration; a
too-early click submits the login form NATIVELY as a GET and sets no cookie. The spec
absorbs this by retrying the interaction (`expect(...).toPass`) until the JS handler's
network call actually fires / the live cart reflects the add.

## Known live gap exercised test-side: DEFECT-D22-02 (region)

The live `AddressIn` requires `region` (`min_length=1`), but the `CheckoutFlow` form
has **no region field** and defaults `region: ""`, and `toBackendAddress` passes it
through verbatim — so a pure-UI checkout 422s on `region`. Following the established
"patch the TEST, not app code" posture (same as the D20 HITL data-spine gap), the
`@live` spec intercepts the outbound `POST /api/orders` body and fills a region so the
live order still PLACES end-to-end (the request still hits `:8000` → DB). **No app code
is touched.** The fix-forward (add a Region input + drop the empty default, or default
a region in `toBackendAddress`) is Iris's — see the Day-22 report.
