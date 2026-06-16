# ADR-0043 — Return window policy + direct-vs-agent return path

Status: Accepted (Day 24, W4D3)
Owner: Orion (backend)

## Context

The returns surface (`POST /orders/{id}/returns`, `GET/PATCH /returns`) went live this
day. Two decisions had no prior ruling and the locked contract (`schemas/returns.py`)
constrains the outcome but not the mechanism:

1. **What is the return window, and what anchors it?** The `ReturnOut.within_window`
   flag is computed server-side. The `Order` / `OrderItem` models carry no
   `delivered_at` timestamp — `OrderStatus` has a `delivered` label but no column. The
   only reliable server-side time anchor on an order is `placed_at`.
2. **How are the DIRECT (non-agent) and AGENT-ASSISTED paths distinguished?** The
   contract locks the outcomes: a DIRECT out-of-window request must return
   `409 return_window_closed`; the AGENT path must instead create the return in
   `hitl_pending` for a human to resolve. The contract does not say how the service
   tells the two paths apart.

## Decision

1. **Window = 30 days from `Order.placed_at`.** `within_window` is true iff the request
   arrives within `RETURN_WINDOW_DAYS` (30) of `placed_at`. `placed_at` is the anchor
   because it is the only dependable server-side timestamp today. The window length is a
   single module constant (`app.services.returns.RETURN_WINDOW_DAYS`) so it is a one-line
   change. Because `within_window` is computed (never client-supplied), moving the anchor
   to a real `delivered_at` later is a service-internal change with no contract impact.

2. **A service-level `allow_hitl` flag selects the path.** `returns.request_return(...,
   allow_hitl: bool = False)`:
   - The HTTP handler (`orders.request_return`) calls with `allow_hitl=False` — the
     strict DIRECT path: out-of-window → `409 return_window_closed`.
   - The agent return/refund tool can call with `allow_hitl=True` — out-of-window →
     create the return in `hitl_pending` (no 409), deferring to a human.
   - In-window requests are identical on both paths (status `requested`).

   This keeps one service entry point for both callers and puts the policy choice in the
   caller's hands rather than sniffing request context inside the service.

## Refund reuse

`PATCH /returns/{id}` with target `refunded` reuses a single shared payment mutation —
`app.services.orders.refund_captured_payment(session, order_id)` (captured → refunded) —
rather than duplicating payment logic in the returns service. The agent `refund` tool's
existing inline mutation is unchanged for now; the shared helper is the seam future
callers (and a later agent refactor) converge on.

## Consequences

- No migration: the `returns` / `return_items` tables already existed (migration 0002).
- A real delivered-at anchor and a per-store window override are both future work that
  this structure absorbs without a contract change.
