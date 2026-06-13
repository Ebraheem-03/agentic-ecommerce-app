# 0022 — Runtime error envelope + CORS wiring (US-E4-01)

Status: accepted · 2026-06-14 · Owner: Orion (backend)

## Context
The contract draft (US-E4-00) defined the canonical error envelope
(`{"error": {code, message, details}}`, closed `ErrorCode` enum) but never wired it
at runtime — FastAPI still emitted its default `{"detail": ...}` for 501/404/422. CORS
did not exist at all, so the Next.js SPA could not call the API cross-origin.

## Decisions
- **Errors live in `app/core/errors.py`**, not alongside `_contract.py`. The contract
  helper is about OpenAPI documentation; runtime exception handling is an app-core
  concern and is imported by `main.py`. `_contract.stub()` now raises the new
  `APIError` (instead of a bare `HTTPException`) so every stub returns the canonical
  envelope.
- **`APIError(status_code, code, message, details=None)`** is the single domain
  exception. A status→`ErrorCode` map (with a 5xx→`internal_error`, else
  →`validation_error` fallback) covers Starlette `HTTPException`s thrown by the
  framework (404, 405, …). `RequestValidationError` → 422 `validation_error` with the
  per-field list under `details.errors`. A catch-all `Exception` → 500 `internal_error`
  with a generic message — internals are never leaked to the client.
- **CORS origins are env-driven** via `HEARTH_CORS_ORIGINS` (comma-separated),
  defaulting to `["http://localhost:3000"]`. The field is annotated `NoDecode` so
  pydantic-settings does not try to JSON-parse the env value; a `before` validator
  splits the comma list. Only `cors_origins` carries the `HEARTH_` alias — the existing
  `DATABASE_URL` / `EMBED_DIM` vars keep their bare names (docker-compose sets those),
  so no global `env_prefix` was added.
- Middleware allows credentials and the `Authorization`, `Content-Type`,
  `Idempotency-Key` headers — the API uses a bearer session token + JSON, and
  idempotency keys land on state-mutating routes in Week 2.

## Consequences
- Every non-2xx response is now contract-shaped; QA can assert on the closed code set.
- Adding a deployed frontend origin is an env change, not a code change.
- No business logic was added to the 501 routers — that stays in Week 2.
