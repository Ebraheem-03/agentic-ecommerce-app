# ADR-0003: Backend hosting: Render or Fly.io (free tier)

- **Status:** Accepted
- **Date:** 2026-06-09

## Context
Need free, Docker-friendly hosting for the FastAPI service.

## Decision
Render (simplest) or Fly.io (best free Docker experience) for the API. Railway kept as fallback (now trial-credit based).

## Consequences
Free tiers cold-start/spin down — acceptable for a demo; note expected first-request latency in the README.
