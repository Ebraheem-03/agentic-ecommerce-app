# ADR-0014: Author logos as code-native SVG instead of Google Stitch

- **Status:** Accepted
- **Date:** 2026-06-10

## Context
CLAUDE.md (§6) assigns Nova the **Google Stitch** skill for the design phase, and US-E2-02 is
written as "3 logo directions via Stitch." In this environment Stitch is not usable for the logo
deliverable: (a) the Stitch MCP is not connected, and (b) Nova runs as a subagent whose sandbox
can't reach it regardless. Stitch also generates full UI **screens/HTML mockups**, not raw logo
geometry — the wrong output shape for a scalable brand mark.

## Decision
Produce the Day-2 logo directions as **hand-authored, dependency-free SVG** (`currentColor`,
clean `viewBox`, no rasters) committed under `docs/brand/assets/`.

## Consequences
- **Better artifact for this stack:** SVG is resolution-independent (24px favicon → 240px), diff-able,
  and hands off directly to Iris's Tailwind/CSS-var work on Day 3 with no export step.
- **Verification gap closed in-repo:** there is no system SVG rasterizer, so we render the SVGs to PNG
  via the already-installed **Playwright/Chromium** (from US-QA-D01) — both a contact-sheet for review
  and a headed Chromium window for the human's `[REVIEW]` pick. This required `npx playwright install
  chromium` once.
- **Process:** Stitch remains the intended tool for screen-level design exploration (Day 3 hi-fi
  screens, US-E2-05) if/when its MCP is wired. This ADR only re-routes the *logo* deliverable.
- Round 1 (3 directions) was rejected; round 2 (6 concepts) → human locked **"Keystone"**. Canonical
  assets: `hearth-logo-mark.svg` + `hearth-logo-lockup.svg`.
