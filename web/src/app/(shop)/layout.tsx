import type { ReactNode } from "react";
import { SiteHeader } from "@/components/shell/SiteHeader";
import { SiteFooter } from "@/components/shell/SiteFooter";

/**
 * App shell for the shopping surfaces: sticky header, skip link, footer. Per the
 * revised ADR-0036 the concierge is no longer a persistent cross-page dock — the
 * conversation lives on the `/search` route (the route IS the conversation). So
 * `AgentProvider` / the streaming state machine are scoped to that page, not the
 * layout, and there is exactly one `agent-chat-panel` in the DOM at a time. Auth
 * pages live in the `(auth)` group with their own minimal chrome.
 */
export default function ShopLayout({
  children,
}: {
  children: ReactNode;
}): JSX.Element {
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:rounded-lg focus:border focus:border-border focus:bg-surface focus:px-3.5 focus:py-2 focus:text-small focus:text-text"
      >
        Skip to content
      </a>
      <SiteHeader />
      <div className="mx-auto flex w-full max-w-[1320px] flex-1 px-4 sm:px-8">
        <main id="main" className="min-w-0 flex-1">
          {children}
        </main>
      </div>
      <SiteFooter />
    </div>
  );
}
