# Roadmap — 4 weeks (read once at week start)

**Build window:** 2026-06-09 → 2026-07-06 (28 calendar days, 7 days/week, daily commits).
**Working agreement:** one story → one feature branch → integration branch → PR to `dev` → (QA + green CI) → PR `dev` → `main`.
**QA agreement:** every day ends with an E2E, contract, data, or eval task. RAGAS coverage must use the current core RAG metrics: context precision, context recall, response relevancy, faithfulness, and agent/tool metrics where applicable.

## Epics
| ID | Epic | Owner(s) | Weeks |
|----|------|----------|-------|
| E1 | Foundations & DevOps (repo, docker, CI skeleton) | Rhea, Atlas | 1 |
| E2 | Design & Branding (brand, logo, tokens, screens) | Nova → Iris | 1 |
| E3 | Database & Data Layer (schema, pgvector, seed) | Sable | 1–2 |
| E4 | Backend Core (FastAPI, Pydantic, Scalar, auth, catalog, cart, orders) | Orion | 2 |
| E5 | Agentic Layer (orchestrator, agents, tools, RAG, guardrails, LLM) | Echo | 2–3 |
| E6 | Frontend (Next.js, generative UI, flows, seller dashboard) | Iris | 3–4 |
| E7 | Integration & QA (tests, e2e, evals, observability) | Juno + all | 1–4 |
| E8 | Deployment & Polish (dev→prod, portfolio readme) | Rhea + all | 4 |

## Milestones
- **End W1:** stack scaffolded, brand + design system approved, DB schema + seed live locally, E2E/RAGAS harness and golden-data baseline started.
- **End W2:** backend core APIs + auth + agent tools done, API E2E suite green, RAGAS dataset seeded, `integration/backend` merged to `dev`.
- **End W3:** full agent layer + frontend core flows, browser E2E suite green against local stack, RAGAS agent/RAG metrics above agreed thresholds, `integration/agents` merged to `dev`.
- **End W4:** full E2E and RAGAS regression gates green, deployed to dev then prod, tagged `v1.0.0`, portfolio README done.

## How to use the day-wise files
Each `week-N.md` lists 7 calendar days with: **ID · story · owner · estimate · autonomy · acceptance criteria**.
Autonomy: `[AFK]` = agent finishes unattended; `[REVIEW]` = stop for the human's decision/taste.
Each day must finish with its `US-QA-Dxx` row before the day's feature branch can merge forward.
Atlas reads **today only** and delegates. Do not load the whole plan at once.
