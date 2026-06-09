# ADR-0006: API documentation via Scalar, not Swagger UI

- **Status:** Accepted
- **Date:** 2026-06-09

## Context
We want modern, readable API docs that look polished in a portfolio.

## Decision
Serve OpenAPI through Scalar; disable/replace the default FastAPI Swagger UI.

## Consequences
Slightly more setup than the default; nicer DX and presentation.
