# ADR-0035 — Frontend component foundation: shadcn/ui on Hearth tokens

- **Status:** Accepted (human-ratified up front, Day 18 / W3D4, 2026-06-26)
- **Owner agent:** Iris (frontend) · ratified by human via Atlas
- **Supersedes/relates:** ADR-0015 (design tokens → code, Tailwind v4 CSS-first), ADR-0017 (hi-fi screens contract)

## Context
Day 18 begins the frontend build. The brand layer is already locked and in-repo:
- Tailwind v4 (CSS-first, no config); every `palette-and-type.md` token as CSS vars on
  `:root` + `[data-theme=dark]`, `@theme inline` mapping (ADR-0015).
- `Button`, `HearthMark`, `ThemeToggle` components + a `/tokens` specimen page already exist
  in `web/src` from the design days.
- 7 token-truthful hi-fi screens (`docs/brand/preview/screens/`) + the `data-testid` registry
  (`docs/qa/test-ids.md`) are the build contract (ADR-0017).

US-E6-02 is `[REVIEW]` — "component choices approved." The open question was the **primitive
foundation** the UI is built on, not the visual design (already locked).

## Decision
Build on **shadcn/ui restyled to Hearth tokens**, with **21st.dev/Magic composing bespoke
pieces on top**.

- shadcn/ui = Radix primitives + owned source copied into our repo (`web/src/components/ui/`).
  We own every file; no runtime/library lock-in; unstyled-by-default so our tokens are the
  single source of visual truth.
- Restyle each primitive to Hearth CSS vars (`--ember`/`--clay`/neutral ramp/semantic) — tokens
  are **not** changed; primitives consume them.
- Radix gives the accessible behavior (focus trap, roving tabindex, ARIA) that US-QA-D18's a11y
  baseline depends on — dialog (cart/checkout), menu, listbox/combobox come correct by default
  instead of being hand-rolled.
- 21st.dev/Magic (Iris's skill) composes the bespoke, on-brand surfaces (agent chat shell,
  generative product cards) on top of the primitive layer; Impeccable is the polish/consistency
  standard over all of it.

## Alternatives considered
- **21st.dev/Magic primary** — faster bespoke pieces, but per-component a11y/consistency varies
  and needs an Impeccable pass each; weaker uniform primitive layer for the QA a11y gate.
- **Hand-roll everything on tokens** — max control, zero new deps, but slowest; re-implements
  accessible dialog/menu/combobox/focus-management from scratch (the exact thing Radix solves).

## Consequences
- Existing `Button` is reconciled to the shadcn pattern (Radix `Slot` + `cva` variants) keeping
  the current ember/clay variants; `HearthMark`/`ThemeToggle` stay.
- New dep surface: `@radix-ui/*` primitives + `class-variance-authority`/`clsx`/`tailwind-merge`
  (standard shadcn deps). TS strict stays on.
- The `data-testid` registry is wired onto the shadcn-based components so the QA layer and the
  hi-fi contract stay 1:1.
