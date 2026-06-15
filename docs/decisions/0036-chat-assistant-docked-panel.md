# ADR-0036 — Conversational shopping assistant = conversation-first search page

- **Status:** Accepted (human-ratified, Day 19 / W3D5, 2026-06-27). **Revised same-day** after a
  rendered review (see "Decision history").
- **Owner agent:** Iris (frontend) · ratified by human via Atlas
- **Relates:** ADR-0017 (hi-fi screens / agent-voice surface), ADR-0021 (agent chat = SSE
  `token→citations→done`), ADR-0035 (shadcn/ui on Hearth tokens), ADR-0031 (LangGraph runtime),
  ADR-0037 (frontend mock SSE + shop clients — unaffected by the layout change)

## Context
Day 19 builds the frontend core flows: US-E6-04 (catalog + search UI with streaming generative
product cards) and US-E6-05 `[REVIEW]` (chat shopping assistant UI — streaming + UI rendering).
The agent turn is an SSE stream (`token → citations → done`, `done` carries `recommendations[]`);
search is also a plain `GET /search?q=` → `SearchResult[]`. How the conversational surface
integrates with the catalog/search page is the architecture-shaping UX fork — and the `[REVIEW]`
acceptance is "UX approved."

## Decision
The shopping assistant is **conversation-first**: the **`/search` route IS the conversation**.

- **`/search` (US-E6-04 + US-E6-05 unified):** a centered chat column. The user types a query
  (`agent-chat-input` / `agent-chat-send`), Ember streams the turn (`thinking` presence →
  token-by-token assistant message → `citations`), and **`done.recommendations[]` render as
  generative product cards INLINE in the assistant's reply** (`agent-recommendation-card` +
  `agent-recommendation-reason`). Discovery is fully agent-driven — there is **no separate
  side-docked panel and no separate full results grid** as the primary surface.
- **Plain `GET /search?q=`** still backs keyword queries; a conversational ask and a plain query
  both resolve into the same in-conversation card stream (the chat column is the single results
  surface). A deep-linkable `?q=` seeds the first turn.
- **Rec/result cards deep-link** into the product detail route (`/product/[idOrSlug]`), which is
  unchanged and stays a traditional PDP.
- **Other pages:** home's hero/entry (`home-hero-cta` / `home-search-entry`) kicks off a
  conversation and navigates into `/search`; the product page can offer an "Ask Ember about this"
  entry that opens `/search` with context. The chat is **not** a persistent cross-page dock.
- Responsive: the conversation column is single-column on mobile; the same `agent-*` testids
  apply. Respect `prefers-reduced-motion` (static thinking indicator).

## Decision history (why this ADR was revised same-day)
The fork was first ratified up front as a **persistent docked right-side panel** (the home
concierge generalized across shop pages). Iris built it (commits `1d55b46`/`809fe87`); Atlas
rendered it in a real Chromium window for the human's `[REVIEW]` sign-off (per the design-review
practice). On seeing it rendered, the human **reworked the layout direction** → chose
**conversation-first**. This ADR is updated to the final ratified direction; the docked-panel
build is superseded and Iris rebuilds the search/chat surface (the PDP, the SSE client, and the
ADR-0037 mock endpoints are reused unchanged).

## Alternatives considered (at the rework)
- **Persistent docked panel** — the initial pick; reworked after rendered review (above).
- **Drawer/overlay from nav** — browse and chat separate, chat opt-in; most conventional but
  weakest agentic presence.
- **Hybrid command-bar** — one top entry, grid-first with an inline answer panel; kept the grid
  as the primary surface, less fully conversational than chosen.

## Consequences
- The `(shop)` layout **drops the persistent `AgentDock`**; the conversation lives on `/search`.
  `AgentProvider`/`agent-store` streaming state machine and the `agent-*` components are reused,
  re-homed into the `/search` conversation column (state scoped to the route, not the layout).
- The PDP (`/product/[idOrSlug]`), the SSE client, and the ADR-0037 mock route handlers
  (`/api/agent/**`, `/api/search`, `/api/cart/items`) are **unchanged** — only the presentation
  shell changes. Flip-to-live at the Day-21 W3 gate is still a config change.
- US-QA-D19 (Juno) targets the conversation-first `/search` (streaming happy path + clarify +
  refusal + error + empty/loading) and the PDP, both viewports, against the mock stream.
