# ADR-0002: Core stack: Next.js + FastAPI + Postgres/pgvector + Docker

- **Status:** Accepted
- **Date:** 2026-06-09

## Context
Portfolio build that must show frontend, backend, AI, and deployment range on free tiers.

## Decision
Next.js (Vercel) frontend; FastAPI (Python) backend; Postgres with pgvector for transactional data + embeddings; Docker for local parity and deploy.

## Consequences
Single Postgres avoids a separate vector DB early. Polyglot (TS + Python) shows range but adds a boundary to maintain.
