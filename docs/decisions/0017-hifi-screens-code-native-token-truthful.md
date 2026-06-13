# ADR-0017: Hi-fi screens as code-native, token-truthful HTML (not Stitch)

- **Status:** Accepted
- **Date:** 2026-06-11
- **Story:** US-E2-05

## Context
CLAUDE.md §6 nominates Google Stitch for Nova's screen layouts. By Day 3 we already
have a real, human-approved token layer in code (`web/src/app/globals.css`, Tailwind v4,
ADR-0015) and a published `data-testid` contract (ADR-0016). Stitch PNGs/exports would
drift from those tokens and carry none of the selector contract, so the hi-fi would not
be truthful to what Iris actually builds.

This extends the precedent of ADR-0014 (logo went code-native SVG instead of Stitch
because the subagent sandbox can't reach Stitch and code-native stayed truthful).

## Decision
Build the 7 hi-fi screens as **self-contained static HTML + CSS** under
`docs/brand/preview/screens/`, that:
1. **Consume the live tokens** — `tokens.css` is a verbatim mirror of `globals.css`
   `:root` + `[data-theme="dark"]`; no invented colour values. `globals.css` stays the
   single source of truth (mirror, accept minor manual-sync cost).
2. **Carry the registered `data-testid`s** (ADR-0016) on every key element, so the
   mockups double as Iris's build contract, not just a picture.
3. Honour the §5 a11y rules (ember CTA = dark ink, announced field errors, etc.).
4. Are rendered in headed Chromium for the human's [REVIEW] sign-off (the project's
   established design-review loop), light theme as the deliverable.

Quantity controls use a conventional **−/value/+ stepper**, not a `<select>` dropdown
(human review note). Product imagery is warm gradient placeholders with a studio
sheen/frame; real photography slots into the same frames at build.

## Consequences
- Easier: hi-fi is truthful to the real token + selector layer; Iris inherits markup +
  IDs directly; reviewable live in a browser; no Stitch auth/sandbox dependency.
- Trade-off: `tokens.css` must be re-synced if `globals.css` changes (manual, low churn);
  these are static mockups, not the Next.js app — they inform the build, Iris reimplements
  as React/Tailwind in a later week.
- Stitch remains available for future ideation; this decision is per-deliverable, not a
  ban (consistent with ADR-0014).
