# ADR-0039 — Flip-to-live deferred to Week 4; W3 gate merges on mocks

- **Status:** Accepted (Atlas analysis + **human-ratified scope call**, Day 21 / W3D7, 2026-06-29)
- **Owner agent:** Atlas (gate); carries to Iris/Echo/Orion for the Week-4 wiring
- **Relates:** ADR-0037 (frontend mock SSE/shop clients), ADR-0038 (agentic
  checkout approval gate), ADR-0023/0024 (auth shapes), ADR-0025/0027 (catalog +
  search), ADR-0028 (order lifecycle / two-step payment), contract-v0.md, and
  US-QA-D21 (the W3 integration gate). **Supersedes** the "flip-to-live = config
  at the W3 gate" expectation stated in ADR-0037 §5 and ADR-0038 §5/Consequences.

## Context
The Week-3 frontend (Days 18–20) was built entirely over same-origin **mock**
route handlers + `web/src/lib/mock/*` (ADR-0037). ADR-0037/0038 anticipated that
the Day-21 W3 gate would be the "flip-to-live" moment — point the env-driven base
URLs at the real backend, wire the agentic-checkout Approve action to the agent
runtime's `interrupt()` resume, "config only."

At the gate Atlas read both trees and found flip-to-live is **not config-only** —
it carries real adapter code. With both lines now in one tree, the assumed shapes
were checked against the live backend (`api/app/schemas/*`):

| Frontend assumption | Live backend (`api/app/schemas`) | Verdict |
|---|---|---|
| catalog/product/rec `price_cents` | `price_minor` / `from_price_minor` (`catalog.py`) | **mismatch** — product surface only |
| cart/order `*_minor` (`unit_price_minor`/`line_total_minor`/`subtotal_minor`/`total_minor`) | same | ✓ already aligned |
| `OrderItemOut.slug` | absent (`order.py`) | derive client-side |
| `OrderDetail.return_eligible` | absent (`order.py`) | compute client-side (status + window) |
| cart-line flat `option_value`/`slug` | `options: dict` (`cart.py`) | flatten client-side |
| auth `{token, expires_at, user}` | `SessionOut{token, expires_at}` + separate `UserOut` (`auth.py`) | minor wrapping adapt |
| (feared) camelCase JSON | `CamelModel` keeps **snake_case** (`envelope.py`) | ✓ no mismatch |

The acceptance criteria for US-QA-D21 are "CI, browser E2E, agent E2E, RAGAS gate
green; PR merged" — all of which both lines already satisfy on their own runtimes
(browser E2E over mocks; agent E2E + RAGAS over the live agent runtime). None of
them require a live frontend↔backend round-trip.

## Decision
**The W3 gate merges both lines to `dev` with the frontend still on ADR-0037
mocks. Flip-to-live is deferred to the Week-4 deploy phase.** (Human scope call,
Day 21 — "merge on mocks, defer flip-to-live.")

The mismatches above become the **Week-4 deploy-wiring spine** (not a config flip):

1. **`price_cents` → `price_minor`** on the catalog/product/recommendation surface
   (`web/src/lib/api-types.ts` `ProductOut`/`from_price`/rec card; `ProductBuyBox.tsx`,
   `RecommendationCard.tsx`). Cart/order already use `*_minor` — no change there.
2. **Derive the three UI-only fields client-side** from what the backend does
   supply: `OrderItemOut.slug` (via product lookup), `OrderDetail.return_eligible`
   (from order status + delivery date vs the return window), cart-line
   `option_value`/`slug` (flatten `options: dict`).
3. **Adapt the auth response wrapping** — `SessionOut{token, expires_at}` + a
   separate `UserOut`, vs the frontend's assumed nested `{token, expires_at, user}`.
4. **Point env bases at the real API** (`NEXT_PUBLIC_API_BASE_URL`,
   `NEXT_PUBLIC_SHOP_API_BASE`, `NEXT_PUBLIC_AGENT_STREAM_BASE`) and wire the
   Approve action to the live agent `interrupt()` resume (ADR-0038).
5. **Resolve two carried product questions** (non-blocking): confirm
   `RegisterRequest.role` rejection of non-buyer/seller roles on self-register;
   and whether the **direct** (non-agent) `POST /orders/{id}/returns` out-of-window
   should defer to `hitl_pending` (frontend's UX choice) vs `409 return_window_closed`.
6. **Add the missing returns data spine** (Day-20 carry): no seed order is both
   `delivered` and out-of-window, so the returns→`hitl_pending` path has no
   deterministic data spine — Juno's E2E drives it test-side today; fix-forward is
   Iris adding a delivered+ineligible seed order to `web/src/lib/mock/orders.ts`
   (or the real seed, once live).

## Consequences
- The W3 PR ships green by code on each line's own runtime; no new app code lands
  at the gate (merge-only) — lowest-risk path, matches the acceptance criteria
  exactly. The Day-7 / Day-14 single-consolidated-PR pattern is preserved (one PR,
  two parent lines reconciled on `integration/w3-gate`).
- The mock layer (ADR-0037) stays the frontend's runtime through `dev`; the
  contract-shape reconciliation is real work owned by Week 4, not a hidden config
  toggle. ADR-0037 §5 and ADR-0038's "swapped at the W3 gate" wording are
  **superseded** by this ADR.
- The agent runtime's live SSE + `interrupt()` resume are proven on the agents
  line (US-QA-D15/D17); the only unproven path is the frontend↔live-backend
  round-trip, which Week-4 deploy wiring + a live E2E will close.
