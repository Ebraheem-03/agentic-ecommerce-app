# ADR-0028 — Order lifecycle, test-mode payment, and inventory reservation

- Status: Accepted
- Date: 2026-06-14
- Story: US-E4-10 (Order create + test-mode payment + lifecycle)
- Owner: Orion (backend)
- Supersedes/extends: ADR-0021 (contract-v0 ratified), aligned with contract-v0 §orders + §1.3

## Context

US-E4-10 turns the `/orders` contract stubs into real handlers: checkout from the open
cart, a two-step test-mode payment, and the inventory bookkeeping that keeps the happy
path from overselling. The approach below was tagged `[REVIEW]` and human-approved
before implementation; this ADR records it.

## Decision

### 1. Order lifecycle (single multi-store order)

`POST /orders` converts the caller's one open cart into a single `Order(status=placed)`
with per-line `OrderItem` snapshots — `title_snapshot`, `options_snapshot`,
`store_name_snapshot`, `unit_price_minor`, `qty` — frozen at checkout (immutable
afterward). The source cart is marked `converted`. An empty/absent open cart is a
`409 empty_cart`. The order moves no further than `placed` in this story
(packed/shipped/delivered/cancelled are later fulfilment work).

`order_number` is human-friendly `HEA-YYYYMMDD-XXXXXX` (UTC date + 6 hex chars). The
`orders.order_number` UNIQUE column is the collision guard.

### 2. Test-mode payment (two-step, deterministic)

No real PSP. `POST /orders/{id}/payment-intent` creates a `Payment(status=pending)`
with a mock `client_secret`/`provider_ref` and `amount_minor = order.total_minor`.
`POST /orders/{id}/payment-confirm` is driven **purely by the request body**:

- `outcome="captured"` (default) → `200 PaymentOut`, payment `captured`.
- `outcome="failed"` → `402 payment_declined`, payment `failed`, **order stays `placed`**
  (unpaid, not cancelled).

No randomness, no env flag, no magic amounts — so QA fixtures (J-BUY-04) are stable.

### 3. Inventory reservation (reserve-at-checkout / capture-on-pay)

`available = qty_on_hand - qty_reserved`.

- **Checkout:** lock each line's inventory row `SELECT … FOR UPDATE`, validate the WHOLE
  cart, then `qty_reserved += qty` per line. Any shortfall fails the entire checkout
  atomically → `409 out_of_stock` (nothing reserved, no order row).
- **Capture (confirm captured):** `qty_on_hand -= qty` AND `qty_reserved -= qty` per line.
- **Decline (confirm failed):** release → `qty_reserved -= qty` per line; order stays
  `placed`.

Both counters are floored at 0 on capture/release so the DB `CHECK (… >= 0)` can never
trip. Reservation is held continuously from checkout until the payment is captured
(reserved→sold) or declined (released).

**Retry-after-decline edge:** a declined confirm releases the reservation. A *fresh*
`payment-intent` on that order re-locks the inventory, re-checks availability, and
re-reserves before issuing the new intent — so a subsequent capture has stock to draw
down. Re-reservation triggers only when the order's most-recent payment is `failed`
(a fresh-checkout order with no payments is already reserved and is not double-reserved).

### 4. Idempotency

A dedicated `idempotency_keys` table (migration **0006**) keyed by
`(user_id, key, endpoint)` stores `(status_code, response_json)`. Checkout,
payment-intent, and payment-confirm consult it first; a replay re-emits the original
result instead of creating a second order/payment. Key source: the `Idempotency-Key`
header (preferred) or `CheckoutRequest.idempotency_key` body fallback. With no key,
routes still run (the one-open-cart→`converted` transition is the secondary guard
against double-checkout). A replayed *decline* re-raises `402` from the stored row.

### 5. Decline persists despite raising `402`

The request-scoped session rolls back on any raised exception (`deps.get_session`). The
decline is a **business outcome**, not a fault: its side effects (release reservation,
payment→`failed`, idempotency row) must persist. So the failed branch `commit()`s
before raising `payment_declined()`.

### 6. Shipping / tax (v0)

Flat **$0 shipping + $0 tax** → `total_minor == subtotal_minor`. Centralized as two
constants in `app/services/orders.py`; the `orders.shipping_minor`/`tax_minor` columns
exist so a real rule can land later with no schema or contract change.

## Consequences

- New table + migration 0006 (proven up→down→up clean); ORM `IdempotencyKey` model and
  the migration/parity table-count expectations bumped 21→22.
- New `ErrorCode` usage: `empty_cart` (409) and `payment_declined` (402) — both already
  present in the closed enum; no new members were needed.
- Concurrency safety rests on row locks; correctness is covered by handler tests
  (`tests/api/test_orders_handlers.py`). Juno owns the end-to-end journey (US-QA-D11).
- The `commit()`-then-raise pattern in the decline branch is intentional and documented
  here so a future refactor doesn't "clean it up" and silently lose the release.
