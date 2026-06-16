# ADR-0045 — Flip returns/seller FE mocks to live; seller fulfil-line backend gap

Date: 2026-07-02 (Day 24, W4D3) · Owner: Iris · Status: Accepted (gap flagged for Atlas/Orion)

## Context
Day-22 (ADR-0040) flipped the happy-path `/api/*` route handlers to live proxies
of FastAPI `:8000`, but left the returns + seller handlers on ADR-0037 mocks
because that backend was unbuilt. Orion + Echo built it on Day 24
(`d38063f`, `17dc6d7`). This ADR flips the remaining four handlers live.

## Decision
Same proxy pattern as ADR-0040 (browser → same-origin `/api/*`; httpOnly token
attached server-side; `{data,meta}`/`{error}` envelope re-wrapped):

- `orders/[id]/returns` — `POST` → live `POST /orders/{id}/returns`; `GET` lists
  via live `GET /returns` then **filters to the order client-side** (there is no
  per-order returns list endpoint). The direct out-of-window `409
  return_window_closed` and the agent path's `hitl_pending` flow straight through.
- `seller/dashboard` — there is **no `/seller/dashboard` aggregate** on the
  backend. It's an FE-only convenience the proxy composes server-side by fanning
  out to live `GET /seller/orders` + `GET /seller/nudges`.
- `seller/nudges/[id]/accept` — live, idempotent; the display-only `accepted`
  flag (not on the backend `NudgeOut`) is set in the proxy on the way out.
- `seller/order-items/[id]/fulfil` — live `PATCH`.

New view-model mapping lives in `web/src/lib/adapters/seller.ts`; the orphaned
`web/src/lib/mock/{returns,seller}.ts` were deleted (`mock/orders.ts` kept — an
e2e spec still imports it).

## The gap (flagged, NOT worked around with invented data)
The seller dashboard's **per-line fulfil table** (`order_items: SellerFulfilItem[]`
— title/options/qty/price/fulfil_status per line) has **no live data source**:

- `GET /seller/orders` returns `OrderSummary[]` (id/number/status/total/
  item_count/placed_at) — **no line items**.
- `PATCH /seller/order-items/{id}/fulfil` also returns only `OrderSummary`.
- `GET /orders/{id}` is **buyer-owner-scoped** → `404` when the seller requests a
  buyer's order detail (verified live).

So a seller cannot enumerate the line ids/snapshots they must fulfil. Per the
brief ("DON'T invent a backend field"), `order_items` and `listings` render
**empty**, the `orders` summaries are surfaced instead, and the fulfil flow is
**unreachable from the UI** until the backend exposes seller-scoped order lines
(items on `OrderSummary` for `/seller/orders`, or a seller `GET /seller/orders/{id}`).
The FE proxies + adapter are correct and ready to populate once that lands.

Other FE-only fields resolved client-side: `NudgeOut.accepted` (set in the accept
proxy), `store_name`/`listings` (neutral/empty — no live source).

## Verification
Live e2e through the Next proxy (DB 55444; seed `mara@makers.hearth.test` /
`ada@buyers.hearth.test`): returns request `201` (requested/within_window) +
filtered list, dashboard fan-out (orders+nudges, `nudge_id==product_id`,
`suggested_change.kind=reprice`), nudge accept (idempotent). Buyer `PATCH
/returns/{id}` → `403 forbidden` as specified. `tsc --noEmit` ✓ · `next lint` ✓.
