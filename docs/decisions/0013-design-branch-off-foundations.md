# ADR-0013: Branch `integration/design` off `integration/foundations`

- **Status:** Accepted
- **Date:** 2026-06-09

## Context
Day 2 brand/design work uses `feature/brand-*` → `integration/design`. The module integration
branches each target `dev`, but `dev` has not yet received the Day-1 foundations (that PR is held
for the Day-7 gate, US-QA-D07). Branching `integration/design` off `dev` would start from the stale
baseline and lose the live `STATUS.md` / `PROGRESS.md` / `DAILY-LOG.md` continuity built on
`integration/foundations`.

## Decision
Branch `integration/design` off **`integration/foundations`** (not `dev`).
- Carries forward the current state docs and the repo scaffold (useful when Day-3 design tokens land).
- `integration/foundations` is clean post-GitGuardian rewrite (no secrets), so no scan risk is inherited.

## Consequences
- At the Day-7 gate, merge order is **`integration/foundations` → `dev` first, then `integration/design` → `dev`**. Once foundations is in `dev`, the design PR diff shows design-only changes (shared base).
- Shared state docs (`STATUS.md` etc.) may need a trivial conflict resolution at Day-7 integration — expected and handled during the dry run.
- Same pattern should apply to later module integration branches that depend on earlier ones.
