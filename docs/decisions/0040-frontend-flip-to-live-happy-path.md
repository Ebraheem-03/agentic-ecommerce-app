# ADR-0040 — Frontend flip-to-live: the happy-path proxy + contract→view-model mapping

- **Status:** Accepted
- **Date:** 2026-06-16 (W4D1 / Day 22)
- **Owner:** Iris (frontend)
- **Context ADRs:** ADR-0037 (FE mock SSE + shop clients), ADR-0039 (flip deferred to W4)

## Context
ADR-0039 deferred the flip-to-live to Week 4 and merged W3 on mocks. Day 22 flips
the **happy-path** surfaces (US-E7-01: search → PDP → cart → checkout → payment →
order status, + the Ember SSE agent) from the ADR-0037 mock fixtures to the live
FastAPI backend, preserving the architecture: the browser only ever calls our
same-origin Next `/api/*` route handlers; those handlers proxy `:8000` server-side
with the httpOnly session token attached. Components are unchanged.

## Decisions
1. **Flip the happy-path route handlers to proxy live**, keep returns + seller on
   mocks (their backend is unbuilt 501 stubs). Each kept-mock handler carries the
   marker `// MOCK until the returns/seller backend lands (Day-22 scope call; ADR-0040).`
2. **Mapping lives in `web/src/lib/adapters/*`** (`catalog.ts`, `order.ts`). The
   backend returns NESTED shapes; the FE view-models are FLAT. Mappers flatten
   search rows, product detail, and agent `done`-frame recommendations
   (`maker←store.name`, `price_cents←from_price_minor` (minor units; legacy name),
   `image_alt←primary_image?.alt`, variant `option_name/value←first options entry`,
   `stock←in_stock ? "in_stock":"out_of_stock"`).
3. **Agent SSE proxy rewrites only the `done` frame** (`web/src/lib/agent-proxy.ts`):
   live `DoneEvent.recommendations[]` are nested `{product, reason}`; we flatten
   each to `AgentRecommendation`. `token`/`citations`/`error` frames — and the
   checkout-approval interrupt/resume frames — pass through verbatim.
4. **`UserOut` aligned to live**: dropped `email_verified` (never consumed in the
   FE), added `is_active`. Auth handlers pass the live `user` straight through.

## Contract mismatches found (not in the brief) and how resolved
- **Checkout address shape.** Live `AddressIn` requires `recipient_name` +
  `country_code` (2-char); the FE form models `name` + `country`. Resolved by
  translating FE→backend in the orders proxy via `toBackendAddress` (the FE country
  field already holds a 2-letter code), so the checkout component is unchanged.
- **Agent `done` recommendations are nested** (`RecommendationOut{product, reason}`)
  and the live `DoneEvent` has no top-level `clarify`/`refusal` fields — handled by
  the `done`-frame transformer in the proxy (point 3).

## Known gap (not a frontend issue)
The live agent emits `event: error` with `GROQ_API_KEY is not set`. The SSE proxy
is verified to forward the live stream correctly (token attached, `text/event-stream`
content-type, frames piped through). The `done`-frame flattening path is unit-correct
against the live `RecommendationOut` schema but cannot be exercised end-to-end until
the LLM key is configured on the backend (Atlas owns live backend env).

## Consequences
- Happy path runs end-to-end against `:8000` with zero mocks (verified: login → PDP
  SSR → add-to-cart → checkout → payment-intent → confirm → order status).
- Returns + seller stay mocked; flipping them is a follow-up story once their
  backend lands.
