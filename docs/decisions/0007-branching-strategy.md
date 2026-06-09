# ADR-0007: Branching: feature → integration → dev → main

- **Status:** Accepted
- **Date:** 2026-06-09

## Context
Need a clear, reviewable flow that demonstrates process maturity with daily commits.

## Decision
`feature/<module>-<slug>` → `integration/<module>` → PR to `dev` (CI gate + Juno QA) → PR `dev` → `main` (release, semver tags).

## Consequences
More branches to manage, but a clean PR history and a real CI/CD story for the portfolio.
