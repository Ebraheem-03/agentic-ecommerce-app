# Week 1 — Foundations · Design · Data
_2026-06-09 → 2026-06-15_  ·  7 days/week  ·  autonomy: `[AFK]` unattended · `[REVIEW]` needs you

## 2026-06-09 (Tue) — Repo & tooling foundation
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E1-01 | Init monorepo (web/, api/, infra/), .gitignore, README, LICENSE | Rhea | 1h | [AFK] | tree matches CLAUDE.md; repo opens clean |
| US-E1-02 | Create `dev` + `main`, document commit/branch conventions | Atlas | 0.5h | [REVIEW] | branches exist; CONTRIBUTING notes Conventional Commits |
| US-E1-03 | Base docker-compose: web + api + Postgres(pgvector) + .env.example | Rhea | 2h | [AFK] | `docker compose up` starts all 3 services |
| US-E1-04 | GitHub Actions skeleton (lint/test/build placeholders) | Rhea | 1h | [AFK] | CI runs green on a no-op |
| US-QA-D01 | E2E harness foundation: test folders, env contract, smoke placeholder, CI slot | Juno | 1h | [AFK] | `e2e` command exists; CI can run a placeholder smoke without app code |

**Git:** `feature/foundation-*` → `integration/foundations`

## 2026-06-10 (Wed) — Brand & design language
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E2-01 | Brand brief: name, tone, audience | Nova | 1h | [REVIEW] | brief approved by you |
| US-E2-02 | 3 logo directions via Stitch | Nova | 2h | [REVIEW] | you pick one direction |
| US-E2-03 | Color palette + typography scale | Nova | 2h | [REVIEW] | palette + type approved |
| US-QA-D02 | QA matrix v0: personas, critical journeys, accessibility checks, RAGAS metric targets | Juno/Nova | 1h | [REVIEW] | matrix covers buyer, seller, support, admin; RAGAS thresholds documented |

**Git:** `feature/brand-*` → `integration/design`

## 2026-06-11 (Thu) — Design system & key screens
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E2-04 | Design tokens → code (Tailwind theme / CSS vars) | Nova/Iris | 2h | [REVIEW] | tokens exported & consumable |
| US-E2-05 | Hi-fi screens: home, search, product, cart, checkout, order status, seller dashboard | Nova | 3h | [REVIEW] | all screens approved |
| US-QA-D03 | UI E2E spec skeleton for home, search, product, cart, checkout, status, seller dashboard | Juno/Iris | 1h | [AFK] | scenarios and stable selectors/test IDs are documented before build starts |

**Git:** `feature/design-system-*` → `integration/design`

## 2026-06-12 (Fri) — Data model design
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E3-01 | ERD: users, products, variants, inventory, carts, orders, order_items, returns, policies, embeddings | Sable | 2h | [REVIEW] | ERD reviewed |
| US-E3-02 | Postgres schema + Alembic migrations + pgvector extension | Sable | 3h | [AFK] | migrations apply on fresh DB |
| US-QA-D04 | DB E2E path: migrate fresh DB, rollback check, seed reset contract | Juno/Sable | 1h | [AFK] | migration test plan covers clean create, rollback, and repeatable local reset |

**Git:** `feature/db-schema-*` → `integration/data`

## 2026-06-13 (Sat) — Seed, data-access & RAGAS data baseline
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E3-03 | Seed data: catalog, users, policies | Sable | 2h | [AFK] | seed populates DB |
| US-E3-04 | SQLAlchemy models / data-access layer | Sable | 2h | [AFK] | models map to schema; unit tests pass |
| US-QA-D05 | Golden eval dataset v0 for catalog/policies RAGAS | Juno/Echo/Sable | 2h | [AFK] | 25 buyer/support questions include expected answer, source docs, and tags |

**Git:** `feature/data-access-*` → `integration/data`

## 2026-06-14 (Sun) — API contracts & E2E fixture design
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-E4-00 | API contract inventory for auth, catalog, search, cart, orders, returns, agent chat | Orion/Juno | 2h | [REVIEW] | route inventory approved; response envelopes and error shapes agreed |
| US-QA-D06 | End-to-end fixture plan: buyer account, seller account, seeded products, payment test-mode, return reasons | Juno/Sable | 2h | [AFK] | fixtures can drive API, browser, and agent tests from one source |

**Git:** `feature/api-contracts-*` → `integration/backend`

## 2026-06-15 (Mon) — W1 integration review
| ID | User story | Owner | Est | Autonomy | Acceptance criteria |
|----|-----------|-------|-----|----------|---------------------|
| US-QA-D07 | W1 full integration dry run + merge to `dev` | Juno/Atlas | 2h | [REVIEW] | docker, migrations, seed, placeholder E2E, and CI are green; PRs merged |

**Git:** PR `integration/foundations|design|data` → `dev`
