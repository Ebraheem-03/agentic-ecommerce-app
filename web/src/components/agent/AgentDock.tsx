"use client";

import { useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useAgent } from "@/components/agent/agent-store";
import { AgentConversation } from "@/components/agent/AgentConversation";
import { AgentHeader } from "@/components/agent/AgentHeader";
import { CloseIcon, EmberMark } from "@/components/agent/agent-icons";

/**
 * The persistent docked concierge surface (ADR-0036). Rendered once at the
 * `(shop)` layout level, so the conversation persists across home / search /
 * product within the shop group.
 *
 *  - Desktop (lg+): a sticky right-side dock in the page gutter.
 *  - Mobile (< lg): a fixed launcher button that opens the SAME conversation in
 *    an accessible bottom sheet (Radix Dialog → focus trap, Escape, scroll lock).
 *
 * Both render `AgentConversation`, so every `agent-*` testid is stable across
 * viewports. The agent panel root carries `agent-chat-panel` + an accessible
 * name (a11y A7) in both. Exactly one panel is ever VISIBLE per breakpoint: the
 * desktop dock is `display:none` below lg (`hidden lg:flex`), and the sheet
 * (with its `lg:hidden` launcher) only mounts on mobile when opened. When the
 * mobile sheet is open the hidden desktop `<aside>` is still in the DOM, so QA
 * should scope to the visible panel (`[data-testid=agent-chat-panel]:visible`).
 */
export function AgentDock(): JSX.Element {
  return (
    <>
      <DesktopDock />
      <MobileSheet />
    </>
  );
}

function DesktopDock(): JSX.Element {
  return (
    <aside
      data-testid="agent-chat-panel"
      aria-label="Ember, the Hearth concierge"
      className="sticky top-[88px] hidden h-[calc(100dvh-112px)] max-h-[760px] w-[360px] flex-none flex-col overflow-hidden rounded-[18px] border border-border bg-surface shadow-[0_1px_2px_rgba(27,22,17,.04),0_18px_44px_-22px_rgba(176,82,46,.28)] lg:flex"
    >
      <AgentHeader />
      <AgentConversation />
    </aside>
  );
}

function MobileSheet(): JSX.Element {
  const [open, setOpen] = useState(false);
  const { busy } = useAgent();

  return (
    <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
      <DialogPrimitive.Trigger asChild>
        <button
          type="button"
          aria-label="Ask Ember, the Hearth concierge"
          className="fixed bottom-5 right-5 z-40 inline-flex items-center gap-2 rounded-full bg-accent px-4 py-3 text-small font-medium text-n-900 shadow-[0_8px_28px_-8px_rgba(176,82,46,.55)] transition-transform hover:scale-[1.03] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 focus-visible:ring-offset-bg motion-reduce:transition-none lg:hidden"
        >
          <EmberMark />
          Ask Ember
          {busy ? (
            <span className="inline-block h-2 w-2 rounded-full bg-n-900/70 motion-safe:animate-pulse" aria-hidden="true" />
          ) : null}
        </button>
      </DialogPrimitive.Trigger>

      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-n-900/50 backdrop-blur-sm data-[state=closed]:opacity-0 data-[state=open]:opacity-100 motion-safe:transition-opacity motion-safe:duration-200 lg:hidden" />
        <DialogPrimitive.Content
          data-testid="agent-chat-panel"
          aria-label="Ember, the Hearth concierge"
          className="fixed inset-x-0 bottom-0 z-50 flex h-[86dvh] flex-col overflow-hidden rounded-t-[20px] border border-border bg-surface shadow-2xl focus:outline-none data-[state=closed]:translate-y-2 data-[state=closed]:opacity-0 motion-safe:transition-[transform,opacity] motion-safe:duration-200 lg:hidden"
        >
          <DialogPrimitive.Title className="sr-only">
            Ember, the Hearth concierge
          </DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">
            Chat with the Hearth shopping assistant. It recommends products with
            reasons, grounded in the catalogue.
          </DialogPrimitive.Description>
          <AgentHeader
            action={
              <DialogPrimitive.Close
                className="grid h-9 w-9 flex-none place-items-center rounded-lg text-text-muted transition-colors hover:bg-surface-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong"
                aria-label="Close concierge"
              >
                <CloseIcon />
              </DialogPrimitive.Close>
            }
          />
          <AgentConversation onNavigate={() => setOpen(false)} />
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
