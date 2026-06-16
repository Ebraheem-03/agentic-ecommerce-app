# ADR-0037 — Frontend mock SSE/search/cart surface + docked-panel state model

- **Status:** Accepted (Iris, Day 19 / W3D5, 2026-06-27)
- **Owner agent:** Iris (frontend)
- **Relates:** ADR-0036 (docked concierge panel), ADR-0035 (shadcn on Hearth
  tokens), ADR-0021 (agent chat = SSE `token→citations→done`), contract-v0.md
  §search / §"Agent SSE event protocol"

## Context
Day 19 builds the catalogue/search UI, product detail, and the streaming chat
assistant — but the backend agent SSE runtime lives on `integration/agents` and
is not running on this line. The frontend must still be developed and E2E-tested
(US-QA-D19) deterministically against the LOCKED contract shapes, with a one-flip
path to the live backend at the W3 gate.

## Decision
1. **Same-origin mock route handlers** under `web/src/app/api/*` serve the
   contract shapes locally, mirroring the Day-18 auth pattern:
   - `POST /api/agent/conversations` and `.../[id]/messages` emit a real
     `text/event-stream` (`token → citations → done`, or terminal `error`) via a
     scripted scenario engine. The event ORDER and payload TYPES are the contract;
     only the strings are placeholder.
   - `GET /api/search?q=` returns the `{ data: SearchResult[], meta: { mode } }`
     envelope. `POST /api/cart/items` returns `CartOut` (201).
2. **Deterministic scenario keys** off the prompt/query so QA can drive every
   path without flake:
   - agent: `refuse`/`ignore your…` → refusal · `which`/`?` (no budget) → clarify
     · `boom` → mid-stream error · else → recommend (cards + citations).
     `?instant=1` collapses inter-frame delays for fast E2E.
   - search: `zzzznoresults` (`EMPTY_QUERY`) → empty state · `boom` → 500.
   - cart: variant `var_bowl_ember` → `409 out_of_stock`.
3. **Transport-only SSE client** (`lib/agent-stream.ts`) parses the byte stream
   into typed frames; a React reducer store (`components/agent/agent-store.tsx`)
   at the `(shop)` layout level runs the streaming state machine
   (`thinking → streaming → done|error`) so the conversation persists across
   navigation (ADR-0036).
4. **Env-driven bases** (`NEXT_PUBLIC_AGENT_STREAM_BASE`, `NEXT_PUBLIC_SHOP_API_BASE`,
   default `/api*`). Flipping to the live backend at W3 is a config change pointing
   these at the API origin; the SSE/search/cart clients and pages are unchanged.
5. **One shared catalogue fixture** (`lib/mock/catalog.ts`) backs search, the
   product detail resolver, and the agent recommendations, so deep-links from a
   rec/search card resolve to a real product page during local dev + E2E.

## Consequences
- US-QA-D19 drives streaming + empty/error/loading/refusal/clarify states fully
  off the mock; no backend dependency on this line.
- The desktop dock and mobile sheet both render `AgentConversation`, so `agent-*`
  testids are identical cross-viewport. Both carry `agent-chat-panel`; exactly one
  is VISIBLE per breakpoint (the hidden one stays in the DOM), so QA scopes to the
  visible panel.
- `lib/mock/*` and `lib/product-data.ts`'s fixture read are the only code paths
  removed at the W3 flip; everything else is contract-shaped already.
