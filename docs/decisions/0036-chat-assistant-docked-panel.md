# ADR-0036 — Conversational shopping assistant = persistent docked panel

- **Status:** Accepted (human-ratified up front, Day 19 / W3D5, 2026-06-27)
- **Owner agent:** Iris (frontend) · ratified by human via Atlas
- **Relates:** ADR-0017 (hi-fi screens / agent-voice surface), ADR-0021 (agent chat = SSE
  `token→citations→done`), ADR-0035 (shadcn/ui on Hearth tokens), ADR-0031 (LangGraph runtime)

## Context
Day 19 builds the frontend core flows: US-E6-04 (catalog + search UI with streaming generative
product cards) and US-E6-05 `[REVIEW]` (chat shopping assistant UI — streaming + UI rendering).
The agent turn is an SSE stream (`token → citations → done`, `done` carries `recommendations[]`);
search is also a plain `GET /search?q=` → `SearchResult[]` grid. How the conversational surface
integrates with the catalog/search page is the architecture-shaping UX fork — and the `[REVIEW]`
acceptance is "UX approved."

## Decision
The shopping assistant is a **persistent docked panel** (right-side dock) that follows the user
across shop pages, matching the approved home concierge (home.html hi-fi).

- **Search page (US-E6-04):** a traditional **results grid** in the main column (`search-results`
  / `search-result-card`), fed by `GET /search?q=`. Plain browse/scan stays first-class.
- **Agent panel (US-E6-05):** the docked `agent-*` surface streams the assistant turn — `token`
  deltas append to the active assistant message, a `thinking` indicator shows presence,
  `citations` render as `agent-citation`, and `done.recommendations[]` render as in-panel
  `agent-recommendation-card` (+ `agent-recommendation-reason` "why"). Rec cards can deep-link
  into the main-column grid / product detail.
- **One chat surface everywhere:** the same docked panel appears on home/search/product (its
  `agent-*` testids are stable cross-screen per the registry), giving the product its agentic
  identity without a separate chat route.

## Alternatives considered
- **Conversation-first search page** (the `/search` route *is* the chat, cards inline in replies)
  — boldest, but discards the traditional browse grid; too far for a portfolio demo that should
  show both paradigms.
- **Drawer/overlay from nav** — keeps browse and chat separate but makes the agent opt-in and
  ever-absent; weakest agentic presence, contradicts the home concierge direction.

## Consequences
- The docked panel is a shared shell-level component (lives alongside the `(shop)` layout), not a
  per-page widget — state persists across navigation within the shop group.
- **Backend SSE runtime is on `integration/agents`, not live on this line.** Iris wires the SSE
  client to the locked contract event shape and drives local dev + the US-QA-D19 E2E from a
  mock/fixture stream (same pattern as Day-18 auth). Real end-to-end streaming is proven at the
  Day-21 W3 gate when both lines merge.
- Responsive: on mobile the dock collapses to an invokable sheet (the panel's `agent-*` testids
  stay identical) so the QA suite runs both viewports.
- US-QA-D19 must cover empty/error/loading + the streaming happy path against the mock stream.
