# 0024 — Allow RFC 6761 `.test` addresses through `EmailStr` (demo)

Status: accepted · 2026-06-17 · Owner: Orion (build) · context: US-E4-04

## Context
The auth handlers (US-E4-04) are the first place the contract's `EmailStr`-typed request
fields (`RegisterRequest.email`, `LoginRequest.email`) meet real input. Every seeded
persona and the entire QA fixture spine (`tests/fixtures/handles.py`) identify accounts
with reserved-TLD addresses — `ada@buyers.hearth.test`, `mara@makers.hearth.test`,
`support@hearth.test`, etc. `.test` is the RFC 6761 special-use TLD reserved *precisely*
for tests and examples, which is why the fixtures chose it.

By default `email-validator` (the library Pydantic v2's `EmailStr` delegates to) rejects
special-use / reserved domains. So `/auth/register` and `/auth/login` would return
`422 validation_error` for **every** seeded persona — which would keep the 6 fixture
persona-login xfails (`test_fixture_spine.py`) red and break all auth-backed E2E journeys.

The seed itself never hit this because it writes emails through the ORM (`Text` column,
no `EmailStr` validation); only the request models validate.

## Decision
On app startup, remove `"test"` (and only `"test"`) from
`email_validator.SPECIAL_USE_DOMAIN_NAMES`. This is the mechanism the library documents
for permitting a reserved TLD in a test/demo environment. Implemented as
`app/core/email_compat.py`, imported by `app/main.py`.

Every other special-use domain (`localhost`, `invalid`, `example`, …) stays rejected, so
the relaxation is narrow and intentional.

## Consequences
- Seeded personas and any `*.test` account validate through `EmailStr`, so the auth
  handlers accept them — flipping the 6 persona-login xfails green.
- This is a **demo/portfolio** accommodation. A production deployment that wanted to reject
  `.test` would not import `email_compat` (or would gate it behind an env flag). Called out
  here so the choice is discoverable rather than a silent global mutation.
- No change to the contract schemas: the field type stays `EmailStr`; only the validator's
  special-use list is tweaked.
