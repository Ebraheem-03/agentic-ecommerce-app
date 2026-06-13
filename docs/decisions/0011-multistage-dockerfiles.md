# ADR-0011: Multi-stage production Dockerfiles (Next standalone, Python wheels)

- **Status:** Accepted
- **Date:** 2026-06-09

## Context
CLAUDE.md §9 calls for production-grade, dockerized deploys (web → Vercel, api → Render/
Fly.io). Even though Vercel builds web itself, a correct prod image keeps Render/Fly.io and
local parity honest. Thin scaffold images should still mirror the real build shape.

## Decision
- **web:** three stages (deps → builder → runner) on `node:20-alpine`, using Next.js
  `output: "standalone"` so the runner copies only the minimal server bundle and runs as a
  non-root `nextjs` user.
- **api:** two stages (builder → runtime) on `python:3.12-slim`; the builder produces wheels
  so the runtime image carries no compiler toolchain, and runs as non-root `appuser`.

## Consequences
Small, rootless final images that are deploy-ready for Render/Fly.io. Both built green
locally and the api image served `GET /health` -> `{"status":"ok"}`. The web image relies on
`output: "standalone"` in `next.config.mjs`; removing that setting would break the runner
stage's COPY of `.next/standalone`.
