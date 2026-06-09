# Week 2 — Backend Core · Agent Tools
_2026-06-16 → 2026-06-22_  ·  7 days/week  ·  autonomy: `[AFK]` unattended · `[REVIEW]` needs you

## 2026-06-16 (Tue) — Backend skeleton & API docs
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E4-01 | FastAPI skeleton, pydantic-settings, health, error envelope | Orion | 2h | [AFK] | app boots; health 200 |
| US-E4-02 | Wire Scalar API docs (replace Swagger UI) | Orion | 1h | [AFK] | /docs renders Scalar |
| US-E4-03 | Pydantic v2 base schemas + response envelope | Orion | 2h | [AFK] | schemas validate; tests pass |
| US-QA-D08 | API E2E smoke: boot stack, health, docs, error envelope, CORS | Juno/Orion | 1.5h | [AFK] | smoke suite runs locally and in CI with deterministic env |

**Git:** `feature/api-*` → `integration/backend`

## 2026-06-17 (Wed) — Authentication & authorization
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E4-04 | Register/login, password hashing, JWT sessions, email-verify stub | Orion | 4h | [REVIEW] | auth endpoints + tests; approach approved |
| US-E4-05 | AuthZ scope middleware (agents act under user scope) | Orion | 2h | [AFK] | scoped access enforced in tests |
| US-QA-D09 | Auth E2E: register, login, refresh/expiry, protected route, scoped denial | Juno/Orion | 2h | [AFK] | positive and negative auth paths pass against real API |

**Git:** `feature/auth-*` → `integration/backend`

## 2026-06-18 (Thu) — Catalog & hybrid search
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E4-06 | Catalog endpoints (list/detail) + inventory | Orion | 2h | [AFK] | endpoints + tests |
| US-E4-07 | Hybrid search endpoint (pgvector + keyword) + rerank stub | Orion/Sable | 3h | [AFK] | relevant results; tests |
| US-E4-08 | Embedding generation on product change | Sable/Echo | 2h | [AFK] | embeddings refresh on update |
| US-QA-D10 | Search E2E + RAGAS retrieval smoke over seeded catalog | Juno/Echo | 2h | [AFK] | context precision/recall smoke scores are captured and failing samples logged |

**Git:** `feature/catalog-*` → `integration/backend`

## 2026-06-19 (Fri) — Cart & orders
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E4-09 | Cart endpoints (add/update/remove, idempotent) | Orion | 2h | [AFK] | idempotent; tests |
| US-E4-10 | Order create + mock/test-mode payment + lifecycle | Orion | 3h | [REVIEW] | order lifecycle; payment approach approved |
| US-QA-D11 | Checkout API E2E: cart mutation, inventory reservation, test payment, order status | Juno/Orion | 2h | [AFK] | idempotency, stock updates, and order lifecycle pass |

**Git:** `feature/orders-*` → `integration/backend`

## 2026-06-20 (Sat) — Agent tools
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E5-01 | Typed tool definitions (search/details/inventory/addToCart/coupon/draftOrder/status/refund) | Echo | 3h | [AFK] | schemas validate |
| US-E5-02 | Tool execution layer (validation + idempotency) | Echo | 2h | [AFK] | tools callable; tests |
| US-QA-D12 | Tool-call E2E: schema validation, auth scope, idempotency, timeout/retry behavior | Juno/Echo | 2h | [AFK] | each tool has success, validation failure, and unauthorized test cases |

**Git:** `feature/tools-*` → `integration/backend`

## 2026-06-21 (Sun) — Backend integration & RAGAS harness
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E7-00 | RAGAS harness implementation: dataset loader, judge config, score artifact, CI-safe sample run | Juno/Echo | 3h | [AFK] | harness can score context precision, context recall, response relevancy, faithfulness |
| US-QA-D13 | Backend regression pack: auth + catalog + search + cart + order + tools | Juno | 3h | [AFK] | full API suite runs from a clean DB seed and emits readable report |

**Git:** `feature/evals-*` → `integration/backend`

## 2026-06-22 (Mon) — W2 review
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-QA-D14 | W2 integration check + merge to `dev` | Juno/Atlas | 2h | [REVIEW] | backend CI, API E2E, tool E2E, and RAGAS smoke are green; PR merged |

**Git:** PR `integration/backend` → `dev`
