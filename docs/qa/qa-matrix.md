# QA Matrix v0 — US-QA-D02

> Status: **✅ Approved (2026-06-10)** — faithfulness gate held at ≥0.90 per human sign-off. Acceptance bar for downstream QA stories.
> Owner: Juno (QA & Integration). Source of truth for personas, journeys, a11y, and RAGAS gates.
> Feeds: E2E specs (US-QA-D03) map 1:1 to journey IDs below; RAGAS thresholds become the
> golden-dataset acceptance bar (US-QA-D05) and the agent eval suite.
> Aligned to `docs/brand/brand-brief.md` (Hearth — "being taken care of"). All numbers are **v0, revisable.**

---

## 1. Personas

| Persona | Goal (one line) | Top success condition | Top failure condition |
|---|---|---|---|
| **Buyer** (delegating buyer) | Get a trusted second opinion that narrows listings and handles checkout — "buying is a conversation, not a hunt." | Agent surfaces a defensible best-value pick with a clear *why*, and checkout completes without tab-sprawl. | Agent recommends an out-of-stock / mispriced / hallucinated item, or buyer is forced back into manual grid-hunting. |
| **Seller** (small seller) | Convert more without learning ad-tech — get told *what to do next*, not just numbers. | Seller lists a SKU and receives an actionable merchandising/pricing nudge they can accept in one step. | Nudge is generic, wrong, or unactionable; listing fails validation silently. |
| **Support** | Resolve order issues with agent assist that is **auditable and honest**. | Agent retrieves the correct order + policy, proposes a correct resolution, and every action is logged/traceable. | Agent fabricates policy or order state, or takes an unlogged action a human can't audit. |
| **Admin** | Oversee catalog, policies, and guardrails with **transparent, controllable** agent behavior. | Admin edits a policy/guardrail and the agent's behavior changes observably and predictably. | Guardrail change has no effect, or agent acts outside configured policy without a visible trace. |

---

## 2. Critical journeys

Stable IDs — **US-QA-D03 E2E specs map 1:1 to these.** "Agent" column = journey exercises the AI/RAG layer.

### Buyer
| ID | Journey | Agent | Edge / HITL note |
|---|---|---|---|
| `J-BUY-01` | Discover: conversational search over catalog | ✅ | Out-of-scope / ambiguous query → graceful clarify, not hallucination |
| `J-BUY-02` | Compare: agent contrasts candidates with reasons | ✅ | Conflicting attributes / missing data surfaced honestly |
| `J-BUY-03` | Add to cart from a recommendation | ✅ | Item went out-of-stock between recommend and add |
| `J-BUY-04` | Checkout (happy path) | — | Payment decline / address validation |
| `J-BUY-05` | Track order / order status | partial | Status lookup for unknown/foreign order id |
| `J-BUY-06` | Return + HITL approval | ✅ | Outside return window → agent defers to human (HITL) |

### Seller
| ID | Journey | Agent | Edge / HITL note |
|---|---|---|---|
| `J-SEL-01` | Onboard seller account | — | Incomplete profile blocks publish |
| `J-SEL-02` | List a product (create SKU) | — | Validation errors are clear + labelled |
| `J-SEL-03` | Receive merchandising/pricing nudge | ✅ | Nudge grounded in real catalog data, not invented |
| `J-SEL-04` | Publish merchandising change (accept nudge) | ✅ | Publish is reversible / audited |
| `J-SEL-05` | Fulfil an order | — | Partial / cancelled fulfilment |

### Support
| ID | Journey | Agent | Edge / HITL note |
|---|---|---|---|
| `J-SUP-01` | Look up order by id / customer | partial | Order not found → honest "no record", no fabrication |
| `J-SUP-02` | Resolve issue with agent assist (policy-grounded) | ✅ | Agent cites policy; refuses out-of-policy resolution |
| `J-SUP-03` | Escalate to human (HITL) + audit log | ✅ | Every agent action is logged and traceable |

### Admin
| ID | Journey | Agent | Edge / HITL note |
|---|---|---|---|
| `J-ADM-01` | Review catalog / policies | — | — |
| `J-ADM-02` | Adjust agent guardrails / policy | ✅ | Change observably alters agent behavior (regression-checked) |
| `J-ADM-03` | Verify guardrail: injection / out-of-scope refusal | ✅ | Prompt-injection resistance; out-of-scope refusal holds |

**Agent-involved journeys** (feed the agent eval suite + RAGAS gates): `J-BUY-01/02/03/06`, `J-SEL-03/04`, `J-SUP-02/03`, `J-ADM-02/03`.

---

## 3. Accessibility checks (WCAG 2.1 AA)

| # | Check | Target | Brand tie-in |
|---|---|---|---|
| A1 | Keyboard navigation | All interactive elements reachable + operable by keyboard; logical tab order; no traps | Conversation-first surfaces must be fully keyboard-drivable |
| A2 | Visible focus state | Every focusable element has a clear, non-color-only focus indicator (WCAG 2.4.7) | — |
| A3 | Color contrast | Text ≥ 4.5:1; large text & UI components / focus indicators ≥ 3:1 (1.4.3 / 1.4.11) | The single brand accent must clear contrast on its surfaces, not just look warm |
| A4 | Reduced motion | `prefers-reduced-motion` honored; non-essential animation disabled | **Agent presence / "thinking" glow must reduce to a static state under reduced-motion** |
| A5 | Semantic landmarks | Proper `header`/`nav`/`main`/`footer`; one `h1`; ordered headings | — |
| A6 | Form labels & errors | Every input programmatically labelled; errors announced + tied to field (3.3.1/3.3.2) | Seller list-product + checkout forms; errors plain-spoken (brand tone) |
| A7 | Screen-reader name for agent chat | Agent chat surface has an accessible name/role; messages announced; "thinking" state exposed via `aria-live`/accessible name, not motion alone | **The agent's presence indicator must have an accessible name, not rely on the glow** |
| A8 | Images / icons | Meaningful images have alt text; decorative ones hidden from AT | Hearth mark decorative where repeated |
| A9 | Target size & spacing | Interactive targets meet AA spacing expectations | — |

Tooling: automated axe pass per page (CI) + manual keyboard/SR spot-checks on agent chat, checkout, and list-product.

---

## 4. RAGAS metric targets (agent RAG layer)

These gate the agent's retrieval-augmented answers. **v0 thresholds, revisable** once the golden dataset (US-QA-D05) gives real distributions.

| Metric | v0 threshold | Rationale (one line) |
|---|---|---|
| **Faithfulness** | ≥ 0.90 | Answers must be grounded in retrieved context — hallucinated policy/catalog claims are the #1 failure mode (support/buyer trust). |
| **Answer relevancy** | ≥ 0.85 | Response must actually address the user's ask; brand promises a useful second opinion, not filler. |
| **Context precision** | ≥ 0.80 | Retrieved chunks should be on-topic; low precision drags faithfulness and inflates token cost on free-tier LLMs. |
| **Context recall** | ≥ 0.85 | The relevant policy/catalog fact must be retrieved at all — high recall protects honesty (no missed return-window / stock fact). |
| **Answer correctness** *(if used)* | ≥ 0.80 | Used only where a labelled ground-truth answer exists (e.g. policy Q&A); composite of semantic + factual match. Optional in v0. |

- These become the **pass/fail acceptance bar** for the golden eval dataset (US-QA-D05) and the agent eval suite (correct tool choice, out-of-scope refusal, prompt-injection resistance, regression checks).
- A journey from §2's agent-involved set should have ≥1 golden case; agent eval runs in CI alongside the E2E gate.
- Thresholds are deliberately conservative-but-achievable for v0; revisit after first real eval run — raise faithfulness/recall first if trust regressions appear.

---

## 5. Traceability note

- **Journeys → E2E (US-QA-D03):** each `J-*` ID above gets exactly one E2E spec, named by ID, in the top-level `e2e/` Playwright workspace. Happy paths: `J-BUY-01→05`, `J-SEL-01→05`, `J-SUP-01`, `J-ADM-01`. Edge/HITL paths: `J-BUY-06` (return+HITL), `J-SEL-04` (merch publish), `J-SUP-02/03`, `J-ADM-02/03`. The fixme stubs in the harness flip to real specs keyed on these IDs.
- **RAGAS targets → golden dataset (US-QA-D05):** the §4 thresholds are the dataset's acceptance bar. Each agent-involved journey contributes labelled cases; the golden set must clear all five metric thresholds plus the agent-eval behavioral checks (tool choice, refusal, injection resistance) before any agent change merges to `dev`.
