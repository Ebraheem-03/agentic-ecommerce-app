# Hearth — DESIGN.md (editorial-gallery direction)

> Build spec for the redesign. Register: **brand-led storefront** (the home/PDP sell the
> craft; search/seller are product UI). Direction **chosen by the human: editorial gallery**,
> built **image-led** so it avoids the saturated "editorial-typographic" slop lane
> (serif + mono labels + ruled columns + NO imagery). Identity is already shipped and is
> PRESERVED: Fraunces (display) + Outfit (body) + the warm clay/ember/oat token system in
> `web/src/app/globals.css`. Do not reflexively reject them — they are the brand.

## Voice (three physical-object words)
Warm · hand-made · unhurried. A maker's studio, not a SaaS landing page.

## What "editorial gallery" means here
- **Photography IS the design.** We now have real curated product imagery (Unsplash, category-matched, 1200px). Let it carry the page: large, full-bleed or near-bleed, generous.
- **Magazine rhythm, not a uniform grid.** Vary card sizes and section composition — a dominant feature image beside smaller supporting ones; asymmetry for emphasis. No identical 3-up / 4-up card walls.
- **Big Fraunces display, intentional whitespace.** Let headings breathe; clamp() fluid scale, max ~5rem (don't shout past 6rem). `text-wrap: balance` on h1–h3.

## Hard guardrails (Impeccable bans — do not violate)
- **NO tiny uppercase tracked eyebrows above sections.** The current home has them on every section ("Curated this week", "Picked for the season", the maker name). Remove them. Find a different cadence (a single strong lead, or let the heading + imagery carry it).
- **NO identical card grids.** Compose; vary.
- **NO em dashes in copy** (and no `--`). The hero copy currently uses one ("with reasons — never hype"). Rewrite with a comma/period.
- **NO gradient text, NO side-stripe borders, NO glassmorphism-by-default.**
- **NO color-block placeholders where a photo belongs.** Collections currently render as bare color gradients; give them real representative imagery (a hero photo per collection) or fold them into an image-led treatment.
- **Contrast:** body text ≥4.5:1. Keep `--text` / `--text-muted`; don't drop muted text onto tinted near-white below 4.5:1.

## Motion
Intentional, restrained. A considered page-load reveal (staggered, fits what it reveals), image hover (subtle scale/lift), `@media (prefers-reduced-motion: reduce)` crossfade/instant alternative for every animation. No bounce/elastic.

## Copy
Specific, not aphoristic. Verb+object buttons ("Start a conversation" is good). No buzzwords. Alt text is part of the voice.

## Surfaces, in priority order
1. **Home** — the hero surface. Image-led hero, an editorial collections feature (asymmetric), the live "picked" rail recomposed (not a flat 4-up), the value strip kept but de-eyebrowed.
2. **Product cards** — the shared unit; larger imagery, quieter metadata.
3. **PDP** — already image-led and decent; tighten to match.
4. **Search** — the conversation; reduce the dead whitespace, give Ember presence.

Keep all existing test-ids (`home-page`, `home-hero-cta`, `home-featured-rail`, etc.) and the shadcn-on-tokens primitives. Tokens are the only source of color — consume them, don't hardcode new hex (the per-card `tone` gradients are the exception being replaced by imagery).
