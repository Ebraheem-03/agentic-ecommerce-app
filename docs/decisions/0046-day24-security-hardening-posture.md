# ADR-0046 — Day-24 security hardening posture + tracked exceptions (US-E7-06)

- **Status:** Accepted
- **Date:** 2026-07-02 (Day 24, W4D3)
- **Deciders:** Human (scope call: "focused audit of the new surface") · Atlas · Orion · Echo
- **Supersedes / relates:** ADR-0033 (refund tiers + injection posture), ADR-0043 (returns window + direct-vs-agent path), ADR-0044 (seller nudges), ADR-0045 (flip-to-live + fulfil-line gap)

## Context

US-E7-06 (security hardening) is tagged `[REVIEW]` with the acceptance criterion
**"no critical gaps; approved exceptions tracked."** Day 24 added genuinely new attack
surface — **returns** (HITL refund path), **seller CRUD/fulfil** (cross-store scope,
incl. the new `GET /seller/orders/{id}` fulfil-line source), and **merch nudges**
(seller-supplied `idempotency_key`). The core controls already existed (session-token
auth + `require_user` scoping; `scan_for_injection` detect-log-refuse; refund tiers
AUTO ≤ $50 / HITL $50–200 / REFUSE > $200 minor units; GitGuardian secret-scan in CI).

The human scoped the pass to a **focused audit of the NEW surface** (not a full
re-audit of settled Week-1/2 controls), proving authz-scope, injection-refusal, and
refund-cap behaviour hold across returns/seller/nudges, with key-free regression tests.

## Decision

The new surface is **audited and locked by regression tests**; all controls hold.
**No critical gaps.** Three exceptions are explicitly approved and tracked below.

### Verified (now pinned by tests)
- **Returns no-leak / role gate** — buyer sees/acts on own returns only; support/admin
  see all; foreign/missing return or order → 404 no-leak; buyer cannot `PATCH`-decide
  (support/admin only → 403). (`app/services/returns.py`; `test_returns_handlers.py`)
- **Seller no-leak / cross-store scope** — `get_order_detail` + `fulfil_item` scope every
  line via variant→product→store; foreign lines/orders → 404 no-leak; unauthenticated →
  401. (`app/services/seller.py`; `test_seller_handlers.py`)
- **Window/HITL fork (ADR-0043)** — direct out-of-window → 409 `return_window_closed`;
  agent path (`allow_hitl=True`) → `hitl_pending`.
- **Nudge guardrail** — the seller-supplied `idempotency_key` is `scan_for_injection`'d
  **before** id resolution / grounding / mutation; injection → 422 + an `agent_actions`
  `action_type='guardrail'` row + no price change. Accept **re-grounds server-side** and
  never trusts a client price; foreign/unknown/market-moved id → 404 no-leak; body
  rejects extra fields (`extra="forbid"`). (`app/services/nudges.py`; `test_seller_nudges.py`)
- **Refund-tier injection resistance** — an injection payload in a refund `reason` cannot
  lift the cap, change identity, or change the amount (all derived structurally from
  `require_user` + `refund_tier(captured.amount_minor)`). (`test_support_agent.py`)

### Approved exceptions (tracked)

1. **Refund cap is the AGENT's ceiling, not the human's.** `decide_return`'s `refunded`
   branch calls `refund_captured_payment` **without** consulting `refund_tier`. This is
   **deliberate** (ADR-0033 §1): the caps bound the *autonomous agent* (enforced in
   `executor._exec_refund`), and the HITL tier explicitly *defers an above-cap refund to
   a human on the support team* — `decide_return` **is** that human resolution / escape
   hatch. Pinned by tests (agent above-cap → 403 refuse, payment untouched; support PATCH
   above-cap → succeeds). **Optional follow-up `[DECISION]` for the human:** if you ever
   want a *hard* ceiling that even support cannot exceed, that is a new policy call — out
   of scope for this hardening slice.

2. **Free-text `note` (return) / `reason` (refund) are not injection-scanned.** Approved
   as **inert**: neither value ever reaches an LLM prompt (`grep note app/agent/` empty;
   `_exec_refund` never reads `args.reason`), and tier/identity/amount are structural. A
   scan here would be redundant. Locked by test rather than adding a no-op scan.

3. **No HTTP-edge rate limiting (DEFECT-D24-01).** The only `rate_limited`/429 path is the
   agent's LLM-call retry budget (`executor.py`), **not** an API throttle. Surfaced by
   Juno's negative matrix (`test_no_http_rate_limit_is_a_known_gap` asserts the gap so it
   flips the moment a limiter lands). **Tracked as DEFECT-D24-01**, deferred to deploy
   hardening (Day 25+) — an edge limiter (e.g. at the Render/Vercel/proxy layer or a
   FastAPI middleware) is the natural home, not per-handler code.

## Consequences

- The Day-24 attack surface is regression-guarded **key-free in CI** (authz/injection/cap
  tests run under pytest with scripted brains — no LLM key).
- DEFECT-D24-01 (no edge rate limiting) is the one open item, deferred to deploy with a
  test already asserting the gap.
- The agent-vs-human refund-cap split is now explicit; a hard support ceiling remains an
  open `[DECISION]` if the human wants it.
