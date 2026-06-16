# ADR-0038 — Agentic checkout: the human-in-the-loop approval gate

- **Status:** Accepted (Iris build, Atlas render → **human-ratified**, Day 20 / W3D6, 2026-06-28)
- **Owner agent:** Iris (frontend), Atlas (review/integration)
- **Relates:** ADR-0036 (conversation-first chat assistant), ADR-0037 (frontend
  mock SSE/shop clients), ADR-0028 (order lifecycle: two-step payment +
  reservation), contract-v0.md §orders / §"two-step payment", and the agent
  layer's checkout-approval `interrupt()` (`integration/agents`)

## Context
US-E6-06 (`[REVIEW]`) builds the cart + the **agentic checkout**. The defining
moment is the human-in-the-loop approval: in the agent runtime, an agent-driven
checkout pauses on a LangGraph `interrupt()` and waits for the buyer to approve
before any money side-effect. The frontend must surface that pause as an explicit
UX gate — not a one-click purchase — and run the contract two-step payment only
on approval. The Day-19 lesson (docked panel → conversation-first rework) said:
**render `[REVIEW]` UX in real Chromium for the human BEFORE locking.** That was
done here.

## Decision
1. **The approval gate is an inline "Approval needed" card in the checkout
   order-summary rail** — *not* a modal overlay and *not* an inline card in the
   `/search` chat transcript. It restates exactly what the agent is about to do
   (items · ship-to · payment · total) with explicit **Approve & place order** /
   **Cancel**, and the standing reassurance *"Nothing is charged until you do."*
   - Considered and rejected at the gate render: a blocking **modal** (heavier
     than warranted; the rail already owns the commit affordance) and a fully
     **chat-inline** gate in `/search` (splits the checkout surface; the
     dedicated `/checkout` page reads clearer for the money step). Both previewed
     for the human; **"lock it as-is" chosen.**
2. **No money side-effect fires before Approve.** Approve runs the contract
   two-step payment: `POST /orders` (idempotent, `Idempotency-Key`) →
   `POST /orders/{id}/payment-intent` → `POST /orders/{id}/payment-confirm`.
3. **Deterministic decline is the contract switch, surfaced as a payment-method
   choice.** "Test card · declined" sends `PaymentConfirmRequest.outcome="failed"`
   → `402 payment_declined`; the order stays placed/unpaid, and Ember offers a
   graceful retry against the same (idempotent) order — no dead end.
4. **Conversation-first voice (ADR-0036) carries through checkout.** Ember frames
   the flow and the gate; the page is concierge-voiced, not a generic wizard.
5. **Mock-first (ADR-0037).** All of cart/checkout/orders/returns/seller runs on
   same-origin mock route handlers + `lib/mock/*`; env-driven bases flip to the
   live API + the real agent `interrupt()` at the W3 gate (config only).

## Consequences
- The gate is the signature surface of the buyer money-path and the UX contract
  Juno's US-QA-D20 full-journey E2E asserts against (search → cart → checkout
  approval → order → status), with an agent-transcript artifact.
- At the Day-21 W3 gate, the mock checkout handlers are swapped for the live
  backend and the approval action is wired to the agent runtime's `interrupt()`
  resume; the UX does not change.
- Open (carried to the human at the gate, non-blocking): a few UI-only convenience
  fields (`OrderItemOut.slug`, cart-line `option_value`/`slug`, `return_eligible`)
  are additive over the Pydantic schemas — confirm the live backend supplies them
  or resolve client-side; and whether the **direct** (non-agent)
  `POST /orders/{id}/returns` out-of-window should defer to `hitl_pending`
  (chosen here for UX) vs return `409 return_window_closed`.
