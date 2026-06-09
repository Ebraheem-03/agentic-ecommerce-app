# Week 3 — Agentic Layer · Frontend
_2026-06-23 → 2026-06-29_  ·  7 days/week  ·  autonomy: `[AFK]` unattended · `[REVIEW]` needs you

## 2026-06-23 (Tue) — Orchestrator & shopping agent
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E5-03 | Orchestrator/router (intent classification) + session state | Echo | 3h | [REVIEW] | routing policy approved; tests |
| US-E5-04 | Shopping agent (discovery, cart, agentic-checkout plan-execute) | Echo | 3h | [AFK] | end-to-end shopping turn works |
| US-QA-D15 | Agent conversation E2E: search intent, product comparison, add-to-cart, checkout approval stop | Juno/Echo | 2h | [AFK] | transcript fixtures pass with tool-call accuracy logged |

**Git:** `feature/agent-*` → `integration/agents`

## 2026-06-24 (Wed) — Support agent · RAG · guardrails
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E5-05 | Hybrid RAG over catalog + policies (with rerank) | Echo | 2h | [AFK] | grounded answers w/ sources |
| US-E5-06 | Support agent (status, returns/refunds + HITL threshold) | Echo | 2h | [REVIEW] | threshold + HITL behavior approved |
| US-E5-07 | Guardrails (I/O validation, injection defense, spend/refund caps) | Echo | 2h | [REVIEW] | guardrail policy approved; injection test passes |
| US-QA-D16 | RAGAS gate v1: support-policy questions, grounded answers, injection/refusal evals | Juno/Echo | 2h | [REVIEW] | scores meet agreed minimums or failures are converted to defects |

**Git:** `feature/agent-*` → `integration/agents`

## 2026-06-25 (Thu) — Merchandising agent & LLM wiring
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E5-08 | Merchandising agent (async generation, comparables pricing, draft) | Echo | 2h | [AFK] | draft listing generated |
| US-E5-09 | LLM routing (Groq/Gemini) + fallback + semantic cache | Echo | 3h | [REVIEW] | provider keys set; fallback works |
| US-QA-D17 | Agent evals: provider fallback, semantic cache hit, merchandising draft quality, tool-call F1 | Juno/Echo | 2h | [AFK] | eval report includes pass/fail, token cost, latency, and failing traces |

**Git:** `feature/agent-*` → `integration/agents`

## 2026-06-26 (Fri) — Frontend foundation
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E6-01 | Next.js scaffold (App Router, TS strict, Tailwind from tokens) | Iris | 2h | [AFK] | app runs; tokens applied |
| US-E6-02 | Component setup (21st.dev) + Impeccable standard | Iris | 2h | [REVIEW] | component choices approved |
| US-E6-03 | Auth UI, layout, nav | Iris | 2h | [AFK] | login/register wired |
| US-QA-D18 | Browser smoke E2E: boot web, route health, auth screens, a11y baseline | Juno/Iris | 2h | [AFK] | Playwright smoke passes with desktop and mobile viewports |

**Git:** `feature/fe-*` → `integration/frontend`

## 2026-06-27 (Sat) — Frontend core flows
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E6-04 | Catalog + search UI with streaming generative product cards | Iris | 3h | [AFK] | cards stream from agent |
| US-E6-05 | Chat shopping assistant UI (streaming + UI rendering) | Iris | 3h | [REVIEW] | UX approved |
| US-QA-D19 | UI E2E: catalog search, product detail, streaming chat, empty/error/loading states | Juno/Iris | 2h | [AFK] | browser suite covers happy path and failure states |

**Git:** `feature/fe-*` → `integration/frontend`

## 2026-06-28 (Sun) — Cart/checkout UI & seller dashboard
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E6-06 | Cart + agentic-checkout UI (approval gate) | Iris | 3h | [REVIEW] | approval gate UX approved |
| US-E6-07 | Order status + returns UI; seller dashboard (merchandising) | Iris | 3h | [AFK] | flows wired end-to-end |
| US-QA-D20 | Full local shopping E2E: search → cart → checkout approval → order → status | Juno/Iris/Echo | 2h | [AFK] | full buyer journey passes with agent transcript artifact |

**Git:** `feature/fe-*` → `integration/frontend`

## 2026-06-29 (Mon) — W3 integration review
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-QA-D21 | FE+agent regression + RAGAS gate + merge to `dev` | Juno/Atlas | 3h | [REVIEW] | CI, browser E2E, agent E2E, and RAGAS gate are green; PR merged |

**Git:** PR `integration/agents|frontend` → `dev`
