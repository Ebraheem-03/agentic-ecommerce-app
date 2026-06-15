import type { ReactNode } from "react";
import { SiteHeader } from "@/components/shell/SiteHeader";
import { SiteFooter } from "@/components/shell/SiteFooter";
import { AgentProvider } from "@/components/agent/agent-store";
import { AgentDock } from "@/components/agent/AgentDock";

/**
 * App shell for the shopping surfaces: sticky header, skip link, footer, and the
 * PERSISTENT docked concierge (Ember). The `AgentProvider` + `AgentDock` live at
 * this layout level (ADR-0036), so the conversation survives navigation across
 * home / search / product within the shop group: page content streams into
 * `main`, the dock sits in the right gutter on desktop and collapses to an
 * invokable sheet on mobile. Auth pages live in the `(auth)` group with their
 * own minimal chrome (no concierge).
 */
export default function ShopLayout({
  children,
}: {
  children: ReactNode;
}): JSX.Element {
  return (
    <AgentProvider>
      <div className="flex min-h-dvh flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:rounded-lg focus:border focus:border-border focus:bg-surface focus:px-3.5 focus:py-2 focus:text-small focus:text-text"
        >
          Skip to content
        </a>
        <SiteHeader />
        <div className="mx-auto flex w-full max-w-[1320px] flex-1 gap-8 px-4 sm:px-8 lg:items-start">
          <main id="main" className="min-w-0 flex-1">
            {children}
          </main>
          <AgentDock />
        </div>
        <SiteFooter />
      </div>
    </AgentProvider>
  );
}
