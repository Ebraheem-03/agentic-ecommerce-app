import { Suspense } from "react";
import { SearchConversation } from "@/components/agent/SearchConversation";

/**
 * `/search` — the conversation IS the route (revised ADR-0036). A centered chat
 * column where the user asks Ember; the turn streams token-by-token and
 * `done.recommendations[]` render as generative product cards inline. There is
 * no separate persistent dock and no separate results grid as the primary
 * surface. A deep-linkable `?q=` seeds the first turn; the SSE stream and the
 * mock route handlers are unchanged.
 *
 * `SearchConversation` is a client component that reads `?q=` (via
 * `useSearchParams`) and mounts the route-scoped `AgentProvider`, so it is
 * wrapped in Suspense.
 */
export default function SearchPage(): JSX.Element {
  return (
    <Suspense
      fallback={<div data-testid="search-page" className="py-16" />}
    >
      <SearchConversation />
    </Suspense>
  );
}
