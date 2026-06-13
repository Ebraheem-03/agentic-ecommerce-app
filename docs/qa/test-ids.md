# Stable `data-testid` registry — US-QA-D03

> Status: **Contract (pre-build).** Documented BEFORE any frontend code so E2E
> selectors are stable from day one.
> Owner: Juno (QA & Integration). Consumers: Iris (frontend build), Nova (screen design).
> Source of journeys: [`qa-matrix.md`](./qa-matrix.md) §2. Each `J-*` journey's E2E
> spec selects elements by the IDs below — **these are a contract, not a suggestion.**

## How to use this registry

- Every element a spec needs to **find, assert, or interact with** has a stable
  `data-testid` here. Iris/Nova must apply these exact values when building the 7 screens.
- **Naming rule:** `kebab-case`, **namespaced by screen** (`<screen>-<element>`),
  with `<screen>-` as the prefix for everything on that screen. Repeating/list rows
  use a `*-line-item` / `*-card` base id plus a per-row `data-testid` is **not** assumed
  unique — specs select the *nth* match or scope within a row. Where a row needs an
  inner anchor, it is listed as `<row-base> > <child>`.
- The **agent chat surface** (`agent-*`) is a shared, cross-screen surface (the product's
  agent voice). Its IDs are stable wherever it appears, so it lives in its own section.
- Only **stable anchors** are registered — not every node. If a spec needs something not
  here, add it to this file in the same PR as the spec, never inline a brittle selector.
- Prefer `getByTestId` (Playwright) over text/role selectors for these anchors so copy
  changes and i18n do not break specs. Role/landmark/a11y assertions (axe, headings,
  focus) still use semantic queries — those are covered by the a11y checks, not test-ids.

---

## Shared: Agent chat surface (`agent-*`)

The conversational surface is the product's core. It appears on home, search, product,
cart, support, and (as the merchandising nudge voice) the seller dashboard. Same IDs everywhere.

| Element | `data-testid` | Notes |
|---|---|---|
| Chat panel root | `agent-chat-panel` | Root container; has accessible name (a11y A7). |
| Presence / "thinking" indicator | `agent-thinking-indicator` | Static under `prefers-reduced-motion`; exposes state via `aria-live` (A4/A7). |
| Message list | `agent-message-list` | Scroll region of turns. |
| A single agent turn | `agent-message-assistant` | One per assistant turn; select nth. |
| A single user turn | `agent-message-user` | One per user turn; select nth. |
| Message input | `agent-chat-input` | Free-text prompt box. |
| Send button | `agent-chat-send` | Submits the prompt. |
| Clarify / disambiguation prompt | `agent-clarify-prompt` | Shown on ambiguous / out-of-scope query (J-BUY-01). |
| Recommendation card (in chat) | `agent-recommendation-card` | Agent's surfaced pick; nth for multiple. |
| Recommendation "why" / reason | `agent-recommendation-reason` | The defensible *why* (J-BUY-02). |
| Refusal / out-of-policy notice | `agent-refusal-notice` | Out-of-scope refusal, injection resistance (J-ADM-03, J-SUP-02). |
| Cited policy / source reference | `agent-citation` | Grounding citation (J-SUP-02). |

---

## Screen 1 — Home (`home-*`)

| Element | `data-testid` | Notes |
|---|---|---|
| Page root | `home-page` | Marker for "landed on home". |
| Hero / primary CTA | `home-hero-cta` | Entry into search/conversation. |
| Search entry box | `home-search-entry` | Opens conversational search. |
| Featured / curated rail | `home-featured-rail` | Optional content row. |
| Header nav | `home-nav` | Global nav; cart link lives here too. |
| Cart link / badge | `home-cart-link` | Count badge for items in cart. |

> The agent chat surface (`agent-*`) may be docked on home; use those IDs, not home-scoped ones.

---

## Screen 2 — Search (`search-*`)

| Element | `data-testid` | Notes |
|---|---|---|
| Page root | `search-page` | "On search results". |
| Search input | `search-input` | The query box. |
| Submit search | `search-submit` | Run the query. |
| Results grid/list | `search-results` | Container of result cards. |
| A single result card | `search-result-card` | One per listing; select nth. |
| Result card title | `search-result-card > search-result-title` | Inner anchor. |
| Result card price | `search-result-card > search-result-price` | Inner anchor. |
| "No results" / empty state | `search-empty-state` | Zero / ambiguous query (J-BUY-01 edge). |
| Filters region | `search-filters` | Faceted refine (optional anchor). |

---

## Screen 3 — Product (`product-*`)

| Element | `data-testid` | Notes |
|---|---|---|
| Page root | `product-page` | "On a product detail page". |
| Title | `product-title` | — |
| Price | `product-price` | — |
| Gallery / main image | `product-image` | Meaningful image → alt text (a11y A8). |
| Add-to-cart button | `product-add-to-cart` | Core action (J-BUY-03). |
| Out-of-stock notice | `product-out-of-stock` | Item OOS between recommend and add (J-BUY-03 edge). |
| Quantity selector | `product-qty` | — |
| "Added to cart" confirmation | `product-add-confirmation` | Toast/inline confirm after add. |

---

## Screen 4 — Cart (`cart-*`)

| Element | `data-testid` | Notes |
|---|---|---|
| Page/drawer root | `cart-page` | "On cart". |
| A line item | `cart-line-item` | One per SKU; select nth or scope within. |
| Line item title | `cart-line-item > cart-line-title` | Inner anchor. |
| Line item qty | `cart-line-item > cart-line-qty` | Editable quantity. |
| Remove line item | `cart-line-item > cart-line-remove` | Inner anchor. |
| Cart subtotal | `cart-subtotal` | — |
| Empty-cart state | `cart-empty-state` | — |
| Proceed to checkout | `cart-checkout-cta` | Hands off to checkout (J-BUY-04). |

---

## Screen 5 — Checkout (`checkout-*`)

| Element | `data-testid` | Notes |
|---|---|---|
| Page root | `checkout-page` | "On checkout". |
| Shipping address form | `checkout-address-form` | Labelled inputs + errors (a11y A6). |
| Address field (line 1) | `checkout-address-line1` | Representative field; add more as needed. |
| Address validation error | `checkout-address-error` | Announced + tied to field (J-BUY-04 edge). |
| Payment form | `checkout-payment-form` | — |
| Payment decline error | `checkout-payment-error` | Decline path (J-BUY-04 edge). |
| Order summary | `checkout-order-summary` | Totals/lines recap. |
| Place order button | `checkout-place-order` | Terminal action of buy flow. |
| Confirmation / order id | `checkout-confirmation` | Post-purchase; surfaces order id for status lookup. |

---

## Screen 6 — Order status (`order-status-*`)

| Element | `data-testid` | Notes |
|---|---|---|
| Page root | `order-status-page` | "On order status". |
| Order id lookup input | `order-status-lookup-input` | Look up by id (J-BUY-05 / J-SUP-01). |
| Lookup submit | `order-status-lookup-submit` | — |
| Status timeline | `order-status-timeline` | Ordered states (placed → shipped → delivered). |
| A timeline step | `order-status-step` | One per state; select nth. |
| Order summary block | `order-status-summary` | Items + totals for the order. |
| "Order not found" state | `order-status-not-found` | Unknown/foreign id → honest, no fabrication (J-BUY-05 / J-SUP-01 edge). |
| Start return CTA | `order-status-return-cta` | Entry into return + HITL (J-BUY-06). |
| Return request panel | `order-status-return-panel` | Return form/flow. |
| HITL "awaiting human" state | `order-status-hitl-pending` | Outside return window → defers to human (J-BUY-06 edge). |

---

## Screen 7 — Seller dashboard (`seller-dashboard-*`)

| Element | `data-testid` | Notes |
|---|---|---|
| Page root | `seller-dashboard-page` | "On seller dashboard". |
| Onboarding panel | `seller-dashboard-onboarding` | Account onboarding (J-SEL-01). |
| Incomplete-profile block | `seller-dashboard-profile-incomplete` | Blocks publish (J-SEL-01 edge). |
| List-a-product form | `seller-dashboard-list-form` | Create SKU; labelled inputs + errors (a11y A6, J-SEL-02). |
| Listing validation error | `seller-dashboard-list-error` | Clear + labelled errors (J-SEL-02 edge). |
| Submit/save listing | `seller-dashboard-list-submit` | — |
| Merchandising/pricing nudge | `seller-dashboard-nudge` | Agent's actionable nudge (J-SEL-03). |
| Nudge grounding / reason | `seller-dashboard-nudge-reason` | Grounded in real catalog data (J-SEL-03 edge). |
| Accept-nudge / publish change | `seller-dashboard-nudge-accept` | One-step accept → publish (J-SEL-04). |
| Publish-reverted / audit notice | `seller-dashboard-publish-audit` | Reversible / audited publish (J-SEL-04 edge). |
| Orders / fulfilment list | `seller-dashboard-orders` | — |
| Fulfil-order action | `seller-dashboard-fulfil` | Mark fulfilled; partial/cancel paths (J-SEL-05). |

> The nudge is the seller-facing voice of the product agent. It is screen-scoped
> (`seller-dashboard-nudge-*`) rather than `agent-*` because it is embedded, not the
> chat panel. The grounding/audit anchors above are what the J-SEL-03/04 specs assert.

---

## Support & Admin surfaces

These journeys (`J-SUP-*`, `J-ADM-*`) reuse the **order status** screen, the **agent
chat surface**, and a thin admin/support console. They do not get their own "screen" in
the 7, but their specs select these IDs:

| Element | `data-testid` | Used by |
|---|---|---|
| Support console root | `support-console` | J-SUP-01/02/03 |
| Order lookup (support) | `order-status-lookup-input` (reused) | J-SUP-01 |
| Agent resolution proposal | `agent-recommendation-card` (reused) | J-SUP-02 |
| Policy citation | `agent-citation` (reused) | J-SUP-02 |
| Escalate-to-human button | `support-escalate-hitl` | J-SUP-03 |
| Audit log entry | `support-audit-log-entry` | J-SUP-03 (every action logged + traceable) |
| Admin console root | `admin-console` | J-ADM-01/02/03 |
| Catalog/policy table | `admin-policy-table` | J-ADM-01 |
| Guardrail editor | `admin-guardrail-editor` | J-ADM-02 |
| Save guardrail | `admin-guardrail-save` | J-ADM-02 |
| Injection-test surface | `agent-chat-input` (reused) | J-ADM-03 (probe via chat) |
| Refusal assertion target | `agent-refusal-notice` (reused) | J-ADM-03 |

---

## Change policy

- Adding a spec that needs a new anchor → add the id **here in the same PR**.
- Renaming an id is a breaking change to every spec that uses it → grep `e2e/` first.
- IDs are environment-agnostic: no ids encode prices, counts, or copy.
