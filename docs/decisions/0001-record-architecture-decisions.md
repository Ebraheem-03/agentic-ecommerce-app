# ADR-0001: Record architecture decisions as ADRs

- **Status:** Accepted
- **Date:** 2026-06-09

## Context
We need durable, low-token memory of *why* choices were made so agents don't relitigate them every session.

## Decision
Every non-obvious decision gets a one-file ADR here. CLAUDE.md and agents reference ADRs instead of carrying rationale inline.

## Consequences
Cheap to read on demand; keeps CLAUDE.md lean; gives the portfolio a visible decision trail.
