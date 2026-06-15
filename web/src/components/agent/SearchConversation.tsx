"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AgentProvider, useAgent } from "@/components/agent/agent-store";
import { AgentConversation } from "@/components/agent/AgentConversation";
import { AgentHeader } from "@/components/agent/AgentHeader";
import { SearchIcon } from "@/components/shell/icons";

/**
 * `/search` — the conversation-first surface (revised ADR-0036). The route IS
 * the conversation: a centered chat column where the user asks Ember, the turn
 * streams, and recommendation cards render inline. `AgentProvider` is mounted
 * HERE (scoped to the route, not the `(shop)` layout), so there is exactly one
 * `agent-chat-panel` / one `agent-chat-input` in the DOM — the old persistent
 * cross-page dock is gone.
 *
 * A deep-linkable `?q=` seeds the FIRST turn (home hero / header search-entry /
 * the thin keyword affordance below push `?q=` and land here). Both a
 * conversational ask and a plain keyword query resolve into the same in-chat
 * card stream.
 *
 * Testids: `search-page` (the conversation root) + `agent-chat-panel` (the
 * accessible-named panel) on the wrapper; `search-input` / `search-submit` on
 * the thin keyword affordance; all `agent-*` testids inside `AgentConversation`.
 */
export function SearchConversation(): JSX.Element {
  return (
    <AgentProvider>
      <ConversationColumn />
    </AgentProvider>
  );
}

function ConversationColumn(): JSX.Element {
  const router = useRouter();
  const params = useSearchParams();
  const q = params.get("q") ?? "";

  const { send } = useAgent();
  const [draft, setDraft] = useState(q);
  // Seed the first turn from the deep-linked `?q=` exactly once per distinct value.
  const seeded = useRef<string | null>(null);

  useEffect(() => {
    setDraft(q);
    const trimmed = q.trim();
    if (trimmed.length > 0 && seeded.current !== trimmed) {
      seeded.current = trimmed;
      send(trimmed);
    }
  }, [q, send]);

  const onSearchSubmit = (e: FormEvent): void => {
    e.preventDefault();
    const next = draft.trim();
    // Push `?q=` so the query is deep-linkable; the effect above seeds the turn.
    router.push(next ? `/search?q=${encodeURIComponent(next)}` : "/search");
  };

  return (
    <section
      data-testid="search-page"
      aria-label="Ember, the Hearth concierge"
      className="mx-auto flex min-h-[calc(100dvh-72px)] w-full max-w-[720px] flex-col py-6 sm:py-8"
    >
      <div
        data-testid="agent-chat-panel"
        aria-label="Ember, the Hearth concierge"
        className="flex min-h-0 flex-1 flex-col"
      >
        <AgentHeader className="-mx-1 rounded-2xl border border-border sm:-mx-2" />

        {/* Thin keyword affordance — carries search-input / search-submit so the
            plain `GET /search?q=` path stays addressable. It seeds a turn. */}
        <form
          onSubmit={onSearchSubmit}
          role="search"
          aria-label="Search the catalogue by keyword"
          className="-mx-1 mt-3 flex items-center gap-2.5 sm:-mx-2"
        >
          <div className="relative flex-1">
            <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-text-muted">
              <SearchIcon />
            </span>
            <input
              data-testid="search-input"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Search makers and goods by keyword…"
              aria-label="Search Hearth by keyword"
              className="h-10 w-full rounded-xl border border-border bg-surface-muted pl-10 pr-3.5 text-small text-text placeholder:text-n-400 transition-colors focus-visible:border-accent-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong/40"
            />
          </div>
          <button
            type="submit"
            data-testid="search-submit"
            className="inline-flex h-10 flex-none items-center rounded-xl border border-border bg-surface px-4 text-small font-medium text-text transition-colors hover:border-accent-strong/60 hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong"
          >
            Search
          </button>
        </form>

        <AgentConversation className="mt-2" />
      </div>
    </section>
  );
}
