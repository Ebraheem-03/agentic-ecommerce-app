# ADR-0029 — Agent tool layer: registry, scope, idempotency + retry, coupon/refund v0 shims

- Status: accepted
- Date: 2026-06-14
- Owner: Echo (AI/Agents)
- Stories: US-E5-01 (typed tool definitions), US-E5-02 (tool execution layer)
- Supersedes / relates: ADR-0028 (order lifecycle/payment), ADR-0021 (agent SSE contract),
  ADR-0026/0027 (embedding/search seams)

## Context

The product's agents need a fixed, typed surface to act through. This ADR covers the
**tool layer only** — typed tool definitions + a callable executor. It does NOT cover the
SSE agent loop or the orchestrator/reasoning agent (later stories). No live LLM call is
made here; everything is provider-agnostic (no Groq/Gemini specifics).

New package: `api/app/agent/` — `tools.py` (8 typed tool defs + registry), `executor.py`
(dispatch + validation + scope + idempotency + retry + audit).

## Decisions

### 1. Registry shape (provider-agnostic)
Each tool is a `ToolSpec`: `name` (closed `ToolName` enum) + `description` +
`input_model` (a Pydantic v2 model, `extra="forbid"`) + flags `mutating` / `sensitive`.
`spec.provider_schema()` returns a plain serializable dict
`{name, description, parameters}` where `parameters` is `input_model.model_json_schema()`.
The agent loop maps that dict onto whichever provider's function-calling shape it uses;
this layer never knows the provider. `tool_specs()` returns the full list.

Outputs reuse existing DTOs where they fit (`ProductDetail`, `CartOut`, `OrderDetail`)
and add small purpose-built models where a tool composes/derives
(`SearchOutput`, `InventoryOutput`, `DraftOrderOutput`, `RefundOutput`, `CouponDiscountOut`).

The 8 tools: `search`, `productDetails`, `inventory`, `orderStatus` (reads);
`addToCart`, `draftOrder` (mutating, idempotent); `refund` (mutating, sensitive);
`applyCoupon` (pure/deterministic).

### 2. One identity path for humans and agents
The executor takes the `User` resolved exactly as HTTP handlers resolve it
(`require_user` / `require_role`, `app/api/deps.py`). There is no separate agent identity.

### 3. Scope policy
- Reads (`search`/`productDetails`/`inventory`/`orderStatus`) — any authenticated user.
- `addToCart`/`draftOrder` — the acting buyer/owner; owner scoping is enforced **inside
  the services** (they 404 on foreign rows, never leaking existence).
- `refund` — **sensitive**: the order owner OR a `support`/`admin` role. An ordinary
  buyer touching a foreign order surfaces `not_found` (no leak), matching the handlers.

A role-class gate (`_check_scope`) is the single seam where a stricter blanket policy
(e.g. "refund always requires support/admin, never owner") would land. Today it is a
no-op because owner-refund is permitted by default — see the `[REVIEW]` flag below.

### 4. Idempotency policy (mutating tools)
`addToCart`/`draftOrder`/`refund` reuse `app/services/idempotency.py` with
`endpoint=f"tool:{name}"`. A replay re-emits the stored result; a stored **error** body
re-raises the same `APIError` status (e.g. a prior `409`). No key ⇒ no replay protection
(the executor still runs). Success bodies are stored as the typed output's JSON and
reconstructed via a per-tool `_REPLAY_OUTPUT` map.

### 5. Retry + timeout policy
Retries are **safe-by-construction**, not best-effort:
- A retryable failure is `TransientToolError`, raised **before any committed side effect**.
  A domain `APIError` (validation/forbidden/not_found/out_of_stock/conflict/...) is a
  definitive answer and is **never** retried.
- For mutating tools the retry runs inside the idempotency guard window, so a committed
  first attempt is replayed rather than double-applied.
- Exhaustion of `max_attempts`, or a per-attempt timeout overrun, raises
  **`APIError(429, rate_limited)`** (chosen over `500` so the caller/agent can back off
  and retry the whole turn — a clean closed-code envelope).
- `RetryPolicy` + injectable `clock`/`sleep` make exhaustion/timeout deterministic for QA.

### 6. Audit
Every terminal path writes an `AgentAction` row (`app/db/models/agent.py`):
`action_type=<tool name>`, `payload` (args + status/replayed, or refusal reason),
`outcome ∈ applied | refused | hitl_deferred`. `conversation_id` may be `None` for
tool-only calls (no conversation yet).

### 7. Shared-session freshness
The agent layer runs many tool calls on ONE long-lived session (unlike the HTTP layer's
fresh per-request session). The executor calls `session.expire_all()` before each
execution so a tool sees committed/flushed effects of earlier tool calls (e.g. a payment
created by `draftOrder` is visible to a later `refund`/`orderStatus`) instead of a stale
identity-mapped relationship collection. `draftOrder` also expires between its internal
checkout and payment-intent calls for the same reason. No service code was changed.

### 8. Errors
All failures raise `APIError(status, ErrorCode.x, msg)` — never a bare `HTTPException`.
**No new `ErrorCode` members were needed**: `validation_error`, `forbidden`, `not_found`,
`conflict`, `rate_limited` all pre-exist in the closed set (`app/schemas/envelope.py`).

## v0 shims + the gaps they leave

### Coupons (`applyCoupon` → `app/services/coupons.py`)
Deterministic stub: a static in-process `_CODES` map (`WELCOME10` → 10%, `HEARTH5` → $5),
case-insensitive match, discount clamped to `[0, subtotal]`. Unknown code → `not_found`.
**GAP (future epic):** no `coupons` table, no per-user redemption ledger, no expiry /
min-spend / stacking, and the discount is computed but NOT persisted onto a cart/order.
The `validate_coupon(code [+ subtotal]) -> CouponDiscount` signature is the stable seam
when a real coupons table lands.

### Refund (`refund`)
Thin v0: marks the order's **captured** `Payment` → `PaymentStatus.refunded` (the enum
member exists) and records the action. No captured payment → `409 conflict`.
**GAP (future epic):** the full returns/refund flow — the returns router is still `501`
(ADR-0028), there is no `Return`/refund ledger linkage, no partial refunds, no
restock-on-refund, and no spend/refund **cap** enforcement yet. The cap + a HITL
threshold are the natural home of the guardrail epic.

## [REVIEW] flag for the human (guardrail policy fork)

**Should an agent be allowed to refund without human approval, and up to what amount?**
v0 default applied here: `refund` is permitted for the **order owner OR a support/admin**
role, recorded as an `applied` audit outcome, with **no spend cap and no HITL threshold**.
This is a sensible build-time default so the layer is usable, but it is a real policy
decision. Recommended follow-up (guardrail epic): add a refund-amount cap + a HITL
threshold above which the action is recorded as `hitl_deferred` instead of `applied`, and
decide whether owner-initiated refunds should require support/admin at all. The
`_check_scope` gate + the `AgentOutcome.hitl_deferred` value are already in place as the
seams for this.

## Consequences
- Tools are callable today against the live services with one typed entrypoint
  (`execute_tool`), ready for the SSE loop to drive.
- QA (US-QA-D12) gets: deterministic retry/timeout (injectable clock), idempotency replay,
  closed-code error envelopes, and an `AgentAction` audit row per call to assert on.
- Two documented debts (coupons table, full returns/refund + guardrail caps) are deferred
  with stable seams, not blocked.
