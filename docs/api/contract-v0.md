# Hearth — API Contract v0 — US-E4-00

> Status: **LOCKED — ratified 2026-06-14** (all 6 [REVIEW] decisions signed off; see §5 + ADR-0021). Owner: Orion (Backend). Day 6 · 2026-06-14.
> Branch: `feature/api-contracts-inventory` (off `integration/backend`). This is the contract Week-2 build stories implement against.
> Scope: auth · catalog · search · cart · orders · returns · agent-chat (+ implied seller & admin).
> This is a **contract preview**: every route handler is a `501 not_implemented` stub so the
> Scalar reference renders the full shape for review. No business logic exists yet.
>
> **Source of truth this maps to:** the 21-table ORM (`api/app/db/models/*`), the 14 native PG
> enums (`alembic/versions/0001_extension_and_enums.py`), the approved ERD (`docs/data/erd.md`),
> the 17 `J-*` journeys (`docs/qa/qa-matrix.md`), and the 7 hi-fi screens' `data-testid` registry.

---

## 1. Conventions

- **IDs:** UUIDv7 strings (server default `uuid_generate_v7()`); always string in JSON.
- **Money:** integer **minor units** (`*_minor`, cents) + 3-letter `currency` (default `USD`) — mirrors the ORM `BigInteger` columns. Never floats for money.
- **Timestamps:** timezone-aware ISO-8601 (e.g. `2026-06-14T10:00:00Z`).
- **Field casing:** **snake_case** everywhere (request + response), matching the ORM and keeping one casing across the stack for v0.
- **Strictness:** request models `extra="forbid"` — unknown fields are a `422 validation_error`.
- **DTOs ≠ ORM:** API schemas live in `api/app/schemas/`, separate from `api/app/db/models/`. Enums are mirrored **by value** in `app/schemas/enums.py`.

### 1.1 Success envelope (proposed)

One envelope for every 2xx:

```jsonc
// single resource
{ "data": { /* resource */ }, "meta": null }

// list
{ "data": [ /* resources */ ], "meta": { "next_cursor": "…", "limit": 24, "total": 137 } }
```

- `meta` is `null` for single-resource responses, a `PageMeta` for lists.
- **Pagination = cursor-based** (opaque `next_cursor`), one style across all list routes. `limit` is 1–100. `total` is best-effort (null when not cheaply known).

### 1.2 Error shape (proposed)

One canonical body for every non-2xx:

```jsonc
{ "error": { "code": "out_of_stock", "message": "Only 2 left of that size.", "details": null } }
```

`code` is a **closed set** (`app/schemas/envelope.py::ErrorCode`) so QA assertions are deterministic.

| `code` | HTTP | When |
|---|---|---|
| `validation_error` | 422 | Request fails schema or a business rule (bad qty, malformed body, unknown field). |
| `unauthenticated` | 401 | Missing / invalid / expired session token. |
| `forbidden` | 403 | Authenticated but wrong role or not the owner. |
| `not_found` | 404 | Resource id doesn't exist or isn't visible to caller. |
| `conflict` | 409 | Generic state conflict (fallback). |
| `cart_already_open` | 409 | Would violate one-open-cart-per-user. |
| `duplicate_review` | 409 | Second review for same (product, user). |
| `email_taken` | 409 | Email already registered among live accounts. |
| `out_of_stock` | 409 | Insufficient inventory at add-to-cart or checkout. |
| `return_window_closed` | 409 | Direct return request outside the window (agent path defers to HITL instead). |
| `empty_cart` | 409 | Checkout attempted with no items. |
| `payment_declined` | 402 | Test-mode payment intent confirmed with `outcome=failed`. |
| `rate_limited` | 429 | Too many requests. |
| `internal_error` | 500 | Unexpected server fault. |
| `not_implemented` | 501 | **Current state of every route in this draft.** |

### 1.3 Auth & idempotency

- **Auth (RATIFIED):** opaque server-side **session token** backed by the `sessions` table (`token_hash`, `expires_at`), sent as `Authorization: Bearer <token>`. Logout = delete the session row. NOT a JWT (so revocation is instant). Implementation calls (hashing, session lifetime, email-verify gate) ratified 2026-06-17 — see **ADR-0023**: argon2id password hashing · **sliding 7-day** token (SHA-256 of a `token_urlsafe(32)` stored) · `email_verified` gate (login `403` while unverified; seed marks personas verified).
- **Idempotency:** state-mutating routes that create money/agent side-effects (checkout, payment-intent, payment-confirm, nudge-accept, agent message) accept an **`Idempotency-Key` header** (preferred) or a body `idempotency_key` fallback. Replays return the original result, not a duplicate.

---

## 2. Route inventory

36 operations (35 API + `/health`). Grouped by resource. Auth column: `—` public, `user` any authenticated, then role. Every route also returns the canonical error envelope on 4xx/5xx.

### auth (`/auth`)
| Method · Path | Purpose | Auth | Request | Response (`data`) | Success | Journey |
|---|---|---|---|---|---|---|
| POST `/auth/register` | Create buyer/seller account | — | `RegisterRequest` | `SessionOut` | 201 | J-SEL-01 |
| POST `/auth/login` | Exchange credentials for token | — | `LoginRequest` | `SessionOut` | 200 | all |
| POST `/auth/logout` | Revoke current session | user | — | `LogoutResult` | 200 | — |
| GET `/auth/me` | Current user | user | — | `UserOut` | 200 | — |

### catalog
| Method · Path | Purpose | Auth | Request | Response | Success | Journey |
|---|---|---|---|---|---|---|
| GET `/products` | Browse/list (filter category, store; paginate) | — | query | `ProductSummary[]` | 200 | J-BUY-01, J-ADM-01 |
| GET `/products/{id}` | Detail (variants, images, rating rollup) | — | — | `ProductDetail` | 200 | J-BUY-02 |
| GET `/products/{id}/reviews` | List reviews | — | query | `ReviewOut[]` | 200 | J-BUY-02 |
| POST `/products/{id}/reviews` | Create review (one per user) | user | `ReviewCreate` | `ReviewOut` | 201 | — |
| GET `/stores/{id}` | Storefront detail | — | — | `StoreDetail` | 200 | J-ADM-01 |

### search
| Method · Path | Purpose | Auth | Request | Response | Success | Journey |
|---|---|---|---|---|---|---|
| GET `/search` | Product search (keyword v0; semantic later) | — | query `q` | `SearchResult[]` | 200 | J-BUY-01 |

> Semantic/pgvector retrieval plugs in behind the same response shape via per-result `score` + response `mode` (`keyword`\|`semantic`\|`hybrid`). **No embedding dimension is baked** — Echo owns that (`EMBED_DIM`).

### cart (`/cart`)
| Method · Path | Purpose | Auth | Request | Response | Success | Journey |
|---|---|---|---|---|---|---|
| GET `/cart` | Get (lazily create) the open cart | user | — | `CartOut` | 200 | J-BUY-03 |
| POST `/cart/items` | Add/increment variant | user | `CartItemAdd` | `CartOut` | 201 | J-BUY-03 |
| PATCH `/cart/items/{id}` | Set line qty (>0) | user | `CartItemUpdate` | `CartOut` | 200 | — |
| DELETE `/cart/items/{id}` | Remove a line | user | — | `CartOut` | 200 | — |

> Honors one-open-cart-per-user (`cart_already_open` if violated), `qty>0` CHECK, unique (cart, variant) (add = upsert). `out_of_stock` when inventory is short.

### orders (`/orders`)
| Method · Path | Purpose | Auth | Request | Response | Success | Journey |
|---|---|---|---|---|---|---|
| POST `/orders` | Checkout: open cart → order (idempotent) | user | `CheckoutRequest` + `Idempotency-Key` | `OrderDetail` | 201 | J-BUY-04 |
| GET `/orders` | List my orders | user | query | `OrderSummary[]` | 200 | J-BUY-05 |
| GET `/orders/{id}` | Order detail + status timeline | user | — | `OrderDetail` | 200 | J-BUY-05 |
| POST `/orders/{id}/payment-intent` | Create TEST-MODE intent | user | `Idempotency-Key` | `PaymentIntentOut` | 201 | J-BUY-04 |
| POST `/orders/{id}/payment-confirm` | Confirm mock intent | user | `PaymentConfirmRequest` | `PaymentOut` | 200 | J-BUY-04 |
| POST `/orders/{id}/returns` | Request a return | user | `ReturnCreate` | `ReturnOut` | 201 | J-BUY-06 |

> **Payment is test-mode only** — no real PSP. Intent→confirm maps to the `payments` table + `payment_status` enum. **Deterministic decline switch (RATIFIED — for Juno's J-BUY-04 fixtures):** `PaymentConfirmRequest.outcome` is the authoritative trigger. Send `outcome="captured"` (the default) for a successful capture; send **`outcome="failed"`** to force a deterministic decline → the confirm returns **`402 payment_declined`** and the payment row lands in `payment_status=failed` (order stays unpaid/`placed`, not cancelled). No magic amounts, no env flag, no randomness — the decline is purely a function of the request body, so fixtures are stable. Order is a single multi-store order with per-item snapshots (title/options/store/unit price frozen).

### returns (`/returns`)
| Method · Path | Purpose | Auth | Request | Response | Success | Journey |
|---|---|---|---|---|---|---|
| GET `/returns` | List returns (own / all by role) | user | query `status` | `ReturnOut[]` | 200 | J-SUP-01 |
| GET `/returns/{id}` | Return detail | user | — | `ReturnOut` | 200 | — |
| PATCH `/returns/{id}` | Decide (approve/reject/refund) | support/admin | `ReturnDecision` | `ReturnOut` | 200 | J-SUP-03 |

> **HITL path:** a return created outside the window via the agent lands in `return_status = hitl_pending`; `PATCH /returns/{id}` is the human resolution endpoint the agent layer + support console drive. (`order-status-hitl-pending` testid.)

### agent — Ember (`/agent`)
| Method · Path | Purpose | Auth | Request | Response | Success | Journey |
|---|---|---|---|---|---|---|
| POST `/agent/conversations` | Start conversation (surface) | user | `ConversationStartRequest` | **SSE stream** (`text/event-stream`) | 201 | J-BUY-01/02, J-SUP-02, J-SEL-03 |
| GET `/agent/conversations/{id}` | Transcript + citations (JSON, not streamed) | user | — | `ConversationOut` | 200 | — |
| GET `/agent/_sse-events` | SSE event payload reference (typed shapes) | user | — | `SseEventCatalog` | 200 | — |
| POST `/agent/conversations/{id}/messages` | Message in → assistant reply **streamed** | user | `MessageRequest` + `Idempotency-Key` | **SSE stream** (`text/event-stream`) | 200 | J-BUY-03/06, J-SUP-02/03 |

> **The contract Echo (Week-2) implements against. The assistant turn is an SSE stream (`text/event-stream`), RATIFIED 2026-06-14 ([REVIEW] decision 5; ADR-0021) — NOT a single JSON body.** Surface ∈ `buyer\|support\|seller`. The REQUEST side is unchanged JSON (`ConversationStartRequest` / `MessageRequest` + optional context order/product ids + `Idempotency-Key`). The transcript GET stays JSON (it reads the persisted conversation). Persists to `conversations`/`messages`/`agent_actions` exactly as before (citations jsonb, `agent_outcome` enum). Model/provider-agnostic. **Note for Iris/Echo Week-2: this is the streaming generative-UI surface.**

#### Agent SSE event protocol

The turn is delivered as ordered `text/event-stream` frames. Each `data:` payload is a typed Pydantic model in `app/schemas/agent.py` (also exposed as a named schema on the Scalar page via `GET /agent/_sse-events` → `SseEventCatalog`):

| `event:` | `data:` payload | Model | Cardinality | Meaning |
|---|---|---|---|---|
| `token` | `"<text delta>"` | `TokenEvent` (`delta`) | 0..n, ordered | A chunk of the assistant message; append in order. |
| `citations` | `[ {source_type, source_id, chunk_index, snippet, score}, … ]` | `CitationsEvent` (`citations[]`) | 0..1 | Grounding citations; emitted when retrieval resolves — **may arrive after some `token` frames**. |
| `done` | `{ conversation_id, message_id, action, recommendations[] }` | `DoneEvent` | 1 (terminal) | Persisted turn: the `agent_actions` row (`action`, whose `outcome ∈ applied\|refused\|hitl_deferred`; null for pure clarify/refusal), any grounded `recommendations`, and the ids to reconcile with the transcript GET. Stream closes after this. |
| `error` | `{ error: { code, message, details } }` | `StreamError` (wraps `ErrorBody`) | 0..1 (terminal) | Stream-level failure — carries the **canonical error envelope** body (closed `code` set) so a mid-stream failure is as machine-checkable as a non-2xx. Stream closes after this. |

Illustrative wire (happy path):

```text
event: token
data: "Let me check"

event: token
data: " our stock."

event: citations
data: [{"source_type":"product","source_id":"…","chunk_index":0,"snippet":"…","score":0.82}]

event: done
data: {"conversation_id":"…","message_id":"…","action":null,"recommendations":[]}
```

The contract-draft route stub yields exactly this ordered `token → citations → done` sequence so the shape is demonstrable; Week-2 swaps in the real agent loop (retrieve → ground → act → persist). The event **order and payload types are the locked contract**; the placeholder strings are not.

### seller (`/seller`) — implied by seller-dashboard + J-SEL-*
| Method · Path | Purpose | Auth | Request | Response | Success | Journey |
|---|---|---|---|---|---|---|
| POST `/seller/store` | Create/complete store profile | seller | `StoreOnboardRequest` | `StoreOut` | 201 | J-SEL-01 |
| POST `/seller/products` | List a product (≥1 variant) | seller | `ProductCreate` | `ProductDetail` | 201 | J-SEL-02 |
| GET `/seller/orders` | Orders to fulfil | seller | query | `OrderSummary[]` | 200 | J-SEL-05 |
| PATCH `/seller/order-items/{id}/fulfil` | Fulfil/cancel a line | seller | `FulfilRequest` | `OrderSummary` | 200 | J-SEL-05 |
| GET `/seller/nudges` | Merchandising nudges (agent-generated) | seller | query | `NudgeOut[]` | 200 | J-SEL-03 |
| POST `/seller/nudges/{id}/accept` | Accept nudge (audited, reversible) | seller | `NudgeAcceptRequest` | `NudgeOut` | 200 | J-SEL-04 |

### admin (`/admin`) — implied by J-ADM-*
| Method · Path | Purpose | Auth | Request | Response | Success | Journey |
|---|---|---|---|---|---|---|
| GET `/admin/policies` | Review policies/guardrails | admin | query `kind` | `PolicyOut[]` | 200 | J-ADM-01 |
| POST `/admin/policies` | Create policy (re-embeds) | admin | `PolicyUpsert` | `PolicyOut` | 201 | J-ADM-02 |
| PUT `/admin/policies/{id}` | Edit policy (re-embeds, bumps version) | admin | `PolicyUpsert` | `PolicyOut` | 200 | J-ADM-02 |

---

## 3. Journey coverage check

All 17 `J-*` journeys have a backing route (agent-involved ones route through `/agent/*` + the underlying resource):
`J-BUY-01` search/agent · `J-BUY-02` product detail/agent · `J-BUY-03` cart add/agent · `J-BUY-04` checkout+payment · `J-BUY-05` orders · `J-BUY-06` returns+HITL ·
`J-SEL-01` store · `J-SEL-02` products · `J-SEL-03` nudges · `J-SEL-04` nudge accept · `J-SEL-05` seller orders/fulfil ·
`J-SUP-01` returns/orders lookup · `J-SUP-02` agent policy-grounded · `J-SUP-03` return decide (HITL/audit) ·
`J-ADM-01` policies list · `J-ADM-02` policy edit · `J-ADM-03` guardrail refusal (exercised via `/agent/*` + `agent_outcome=refused`).

---

## 4. Schema gaps noted (NOT changed — for Sable/human)

These are contract needs that the current schema doesn't obviously cover. **No migration/ORM was touched**; flagging only:

1. **Return window source.** `returns.within_window` is a stored bool, but no column records the window length or the policy it derived from. v0 can compute it from a `policy_kind='returns'` policy at request time; if we want auditability we may later want a `window_days` snapshot on the order/return. *(Open — does not block the contract.)*
2. **Guardrail config storage.** Admin "adjust guardrails" (J-ADM-02/03) has no dedicated table; v0 maps guardrails onto `policies` with `kind='platform'`. Works, but a future `guardrails` table may be cleaner. *(Open.)*
3. **Order ↔ seller link for `/seller/orders`.** Sellers are reached only via `order_items.store_name_snapshot` (a string) — there's no `store_id` on `order_items`. Filtering a seller's orders needs the join `order_items.variant_id → variants → products.store_id`, which breaks for `variant_id = NULL` (deleted variant). *(Open — likely fine for v0 since deletes are rare; note for Sable.)*
4. **Nudges have no table.** `NudgeOut` is agent-generated and (in v0) ephemeral / derived; accepting one writes an `agent_actions` row. If nudges must persist, that's a new table for Echo/Sable. *(Open.)*

---

## 5. DECISIONS — RATIFIED 2026-06-14

The six [REVIEW] questions are signed off by the human. This section is the locked record of truth; the durable rationale lives in **ADR-0021**. Week-2 build stories implement against these.

| # | Decision | Ruling (RATIFIED) |
|---|---|---|
| 1 | **Auth mechanism** | ✅ **Opaque server-side session token** — backed by `sessions(token_hash, expires_at)`; `Authorization: Bearer <token>`; logout = delete row → instant revocation. NOT a JWT. *(Draft default kept.)* **Impl calls ratified 2026-06-17 (ADR-0023):** argon2id hashing · sliding 7-day token (SHA-256 stored) · `email_verified` gate (login `403` while unverified; auth-backed seeding marks personas verified → flips the 6 login xfails). |
| 2 | **Response envelope** | ✅ **Wrapped `{data, meta}`** — single envelope; pagination in `meta`; mirrors the error envelope. *(Draft default kept.)* |
| 3 | **Pagination** | ✅ **Opaque cursor** in `meta.next_cursor`, one style across all list routes; `limit` 1–100; `total` best-effort. *(Draft default kept.)* |
| 4 | **Search v0** | ✅ **Keyword-only, semantic-ready** — response carries per-result `score` + a top-level `mode` discriminator (`SearchMode`: `keyword`\|`semantic`\|`hybrid`) now; pgvector retrieval drops in behind the same shape with **no contract change**. Stay embedding-agnostic (no `EMBED_DIM` baked); **pgvector deferred to Echo, Week-2**. *(Draft default kept.)* |
| 5 | **Agent chat** | ✅ **SSE STREAMING** (`text/event-stream`) — **CHANGED from the draft's single-JSON `AgentReply`.** Event protocol `token → citations → done` (+ `error`), each `data:` payload a typed model (`TokenEvent` / `CitationsEvent` / `DoneEvent` / `StreamError`). Request side + persisted entities (conversations/messages/agent_actions, citations jsonb, `agent_outcome` enum) unchanged. See §"Agent SSE event protocol". This is the Week-2 streaming generative-UI surface for Iris/Echo. |
| 6 | **Test-mode payment** | ✅ **Two-step intent → confirm** with a **deterministic decline switch**: `PaymentConfirmRequest.outcome="failed"` → `402 payment_declined`, payment row `failed`, order stays `placed`. Drives J-BUY-04's failed-checkout path with stable fixtures (no magic amount / env flag / randomness). *(Draft default kept; decline mechanism documented for Juno.)* |

> Locked. Atlas FF-merges `feature/api-contracts-inventory` → `integration/backend`; Week-2 build stories implement handlers against these types.
