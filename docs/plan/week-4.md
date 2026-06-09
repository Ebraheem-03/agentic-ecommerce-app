# Week 4 — Integration · QA · Deploy · Polish
_2026-06-30 → 2026-07-06_  ·  7 days/week  ·  autonomy: `[AFK]` unattended · `[REVIEW]` needs you

## 2026-06-30 (Tue) — End-to-end integration
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E7-01 | E2E happy path (search → cart → checkout → order → status) | Juno | 3h | [AFK] | happy path passes locally and in CI |
| US-E7-02 | E2E returns + HITL and merchandising publish | Juno | 2h | [AFK] | edge paths pass with seeded buyer/seller accounts |
| US-E7-03 | Fix integration defects | area owner | 2h | [AFK] | defects closed or explicitly deferred |
| US-QA-D22 | Daily full-stack regression: API, browser, agent, RAGAS smoke | Juno/all | 2h | [AFK] | all critical journeys have artifacts and failing cases are filed |

**Git:** `feature/e2e-*` → `integration/frontend`

## 2026-07-01 (Wed) — Hardening & observability
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E7-04 | Tracing/observability + token/cost logging | Echo/Rhea | 3h | [AFK] | traces visible per agent run |
| US-E7-05 | Agent eval suite with RAGAS + tool metrics | Echo/Juno | 3h | [REVIEW] | context precision/recall, response relevancy, faithfulness, tool-call accuracy/F1, and goal accuracy are gated |
| US-QA-D23 | Observability E2E: trace every user journey and attach eval/test run IDs | Juno/Echo/Rhea | 2h | [AFK] | failing E2E/RAGAS cases link to trace, prompt, tool calls, and cost |

**Git:** `feature/obs-*` → `integration/frontend`

## 2026-07-02 (Thu) — Security, performance & accessibility
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E7-06 | Security hardening: auth scope audit, prompt injection suite, spend/refund limits, secret scan | Orion/Echo/Rhea | 3h | [REVIEW] | no critical gaps; approved exceptions tracked |
| US-E7-07 | Performance and accessibility pass: API latency, streaming UX, Lighthouse/a11y checks | Iris/Orion/Juno | 3h | [AFK] | agreed budgets met or defects created |
| US-QA-D24 | Negative E2E matrix: unauthorized access, stale inventory, payment failure, injection, rate limit | Juno/all | 2h | [AFK] | all negative cases have deterministic pass/fail assertions |

**Git:** `feature/hardening-*` → `integration/frontend`

## 2026-07-03 (Fri) — Dev deploy
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E8-01 | Prod-ready multi-stage Dockerfiles | Rhea | 2h | [AFK] | images build small & run |
| US-E8-02 | Deploy api→Render/Fly, db→Supabase/Neon, web→Vercel (dev env) | Rhea | 3h | [REVIEW] | dev env live; needs your accounts/keys |
| US-E8-03 | CI/CD: auto-deploy dev on `dev` merge | Rhea | 2h | [AFK] | dev deploy on merge |
| US-QA-D25 | Deployed-dev E2E + RAGAS run against dev URLs | Juno/Rhea | 2h | [AFK] | dev smoke, browser journey, API suite, and RAGAS sample pass against hosted env |

**Git:** PR `integration/frontend` → `dev`

## 2026-07-04 (Sat) — Release candidate regression
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E8-04 | Release candidate checklist: env vars, backup/rollback, monitoring alerts, runbooks | Rhea/Atlas | 2h | [REVIEW] | release checklist approved |
| US-QA-D26 | RC full regression: all E2E journeys, API contracts, RAGAS full set, visual/a11y snapshots | Juno/all | 4h | [AFK] | no blocker defects; report attached to release candidate |

**Git:** `release/v1.0.0-rc` → `dev`

## 2026-07-05 (Sun) — Portfolio polish & demo proof
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E8-05 | Portfolio README + architecture diagram + demo script + screenshots | Atlas/Nova | 3h | [REVIEW] | README portfolio-ready |
| US-QA-D27 | Demo E2E rehearsal: scripted recording path, seeded data reset, RAGAS summary table | Juno/Atlas | 2h | [AFK] | demo script completes twice from clean seed; eval summary is screenshot-ready |

**Git:** `feature/portfolio-*` → `dev`

## 2026-07-06 (Mon) — Prod promotion
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E8-06 | Promote dev→main, prod deploy, smoke test | Rhea/Atlas | 2h | [REVIEW] | go/no-go; prod live |
| US-E8-07 | Tag release v1.0.0 | Atlas | 0.5h | [AFK] | tag pushed |
| US-QA-D28 | Final prod smoke: health, auth, search, checkout, order status, support RAG, monitoring alert | Juno/Rhea | 2h | [AFK] | prod smoke and final RAGAS sample pass; release notes include evidence links |

**Git:** PR `dev` → `main`; tag `v1.0.0`
