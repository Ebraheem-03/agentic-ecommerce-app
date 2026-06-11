# ADR 0015 — Tailwind v4 token model + build-time font fetch (US-E2-04)

Status: Accepted · 2026-06-11 · Iris

## Context
Day 3 turns the locked palette/type spec into code. Atlas pre-decided Tailwind v4
(CSS-first). Fonts (Fraunces, Outfit) load via `next/font/google`, which fetches
from Google Fonts at **build time**.

## Decisions
1. **Token model.** Raw hex lives only in `web/src/app/globals.css`, emitted as
   CSS custom properties on `:root` (light) and `[data-theme="dark"]` (dark).
   `@theme inline` maps role tokens (`--color-bg`, `--color-brand`, …) and the §6
   type scale into Tailwind utilities. `inline` is required so utilities resolve
   to the live `var()` and follow `[data-theme]` swaps.
2. **Dark ink for the ember CTA.** The spec's canonical primary CTA is ember fill
   with dark ink `#1b1611` in **both** themes. No single role token is dark in
   both (`--text` flips off-white on dark; `--on-accent` flips white on light), so
   the Button uses `--n-900` (always `#1b1611`) for the primary ink. Faithful to
   §5 rule 1 (6.7:1).
3. **PRODUCT.md not created.** Impeccable's setup wants a PRODUCT.md; this is a
   focused token story with identity already committed in `docs/brand/`. Followed
   Impeccable's *General rules* (contrast, motion + reduced-motion, semantics)
   without scoping-creeping a PRODUCT.md. Revisit if a later story wants the full
   Impeccable init.

## Build-environment note (for Rhea / CI)
`next/font/google` fetches at build time. In some sandboxes node's fetch hangs on
IPv6 (happy-eyeballs) while IPv4 works. Workaround used locally to get a green
`npm run build`:

```
NODE_OPTIONS="--dns-result-order=ipv4first --no-network-family-autoselection" npm run build
```

CI/Vercel with normal egress should not need this. If CI ever shows
`Failed to fetch Fraunces/Outfit from Google Fonts`, set that NODE_OPTIONS or
self-host the four font files.
