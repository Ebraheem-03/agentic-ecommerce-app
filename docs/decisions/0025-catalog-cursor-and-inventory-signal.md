# ADR-0025 — Catalog: keyset cursor pagination, id-or-slug lookup, inventory signal

Status: Accepted · 2026-06-18 · Owner: Orion (Backend) · Story: US-E4-06

## Context

Catalog list/detail + store detail go live against contract-v0, which locks a
`{data, meta}` envelope with **opaque cursor** pagination (`meta.next_cursor`,
`limit` 1–100, best-effort `total`) and a per-variant `in_stock` boolean as the
only stock signal in the schema. Three implementation choices weren't spelled out
by the contract and are recorded here.

## Decisions

1. **Keyset cursor, not OFFSET.** The opaque `next_cursor` is a base64url-wrapped
   keyset position `(created_at, id)` of the last row on the page; the next query
   asks for rows strictly after it in `created_at DESC, id DESC` order, fetching
   `limit + 1` to detect "has more" without a second COUNT. Keyset gives stable,
   drift-free paging under concurrent inserts (OFFSET skips/repeats rows). The
   helper lives in `app/api/pagination.py` so every future list route (orders,
   search, returns) paginates identically. A malformed cursor → `422
   validation_error` (closed code), not a 500. `total` is sent as `null`
   (best-effort, as the contract allows) — no COUNT on the list path.

2. **id-or-slug lookup guards the UUID cast.** `GET /products/{id_or_slug}` and
   `GET /stores/{id_or_slug}` accept either. The id columns are typed Postgres
   `UUID`; OR-ing `id == <slug>` makes PG try to cast the slug to a UUID and raise
   a `DataError`. So the id comparison is only OR-ed in when the path segment
   actually parses as a `uuid.UUID`; otherwise we match slug only. Missing →
   canonical `404 not_found`.

3. **Inventory surfaces as a boolean, per the schema.** `VariantOut.in_stock` =
   `(qty_on_hand - qty_reserved) > 0`; a variant with no inventory row counts as
   out of stock. `restock_eta_days` passes through. The contract's `VariantOut`
   has **no** low/oos enum — `in_stock` is the locked signal — so the seeded
   low-stock variant (qty 3) surfaces `in_stock=true` with a restock eta, and the
   OOS variant (qty 0) surfaces `in_stock=false`. Exact counts stay private. A
   richer stock-state enum would be a contract change (out of scope here).

## Consequences

- Reads are public (no auth), eager-load store/images/variants/inventory
  (`selectinload`) to avoid N+1, and filter to `status='active'` + not soft-deleted.
- The pagination helper is reusable; adopting it elsewhere is a follow-up, not a
  rewrite. Reviews list/create remain contract stubs (separate story).
