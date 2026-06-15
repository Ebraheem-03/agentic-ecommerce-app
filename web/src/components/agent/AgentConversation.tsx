"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { cn } from "@/lib/cn";
import type { AssistantTurn, Turn } from "@/components/agent/agent-store";
import { useAgent } from "@/components/agent/agent-store";
import { RecommendationCard } from "@/components/agent/RecommendationCard";
import { CitationIcon, SendIcon } from "@/components/agent/agent-icons";

/**
 * The Ember conversation body — message list + composer. Shared verbatim by the
 * desktop dock and the mobile sheet, so every `agent-*` testid is stable across
 * viewports (ADR-0036). Reads the streaming state machine from `useAgent`.
 *
 * Rendered states: user turn, assistant turn (thinking → streaming → done),
 * citations, recommendation cards + reason, clarify prompt, refusal notice,
 * error. The thinking indicator is `aria-live` and goes static under
 * `prefers-reduced-motion` (the animated dots are gated by `motion-reduce`).
 */

const STARTERS = [
  "A wedding gift for a couple who love to cook, around $90",
  "Something warm for a small living room",
  "Show me ceramics under $50",
];

export function AgentConversation({
  onNavigate,
  className,
}: {
  onNavigate?: () => void;
  className?: string;
}): JSX.Element {
  const { turns, busy, send } = useAgent();
  const [draft, setDraft] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  // Keep the newest turn in view as tokens stream in.
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [turns]);

  const submit = (text: string): void => {
    const t = text.trim();
    if (!t || busy) return;
    send(t);
    setDraft("");
  };

  const onSubmit = (e: FormEvent): void => {
    e.preventDefault();
    submit(draft);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>): void => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit(draft);
    }
  };

  const isEmpty = turns.length === 0;

  return (
    <div className={cn("flex min-h-0 flex-1 flex-col", className)}>
      <div
        ref={listRef}
        data-testid="agent-message-list"
        role="log"
        aria-label="Conversation with Ember, the Hearth concierge"
        aria-live="polite"
        tabIndex={0}
        className="flex flex-1 flex-col gap-3.5 overflow-y-auto p-[18px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-inset"
      >
        {isEmpty ? (
          <EmptyState onPick={submit} />
        ) : (
          turns.map((turn) => (
            <TurnView key={turn.id} turn={turn} onNavigate={onNavigate} />
          ))
        )}
      </div>

      <form
        onSubmit={onSubmit}
        className="flex items-end gap-2.5 border-t border-border bg-surface p-3"
      >
        <textarea
          data-testid="agent-chat-input"
          rows={1}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={busy}
          placeholder="Describe what you’re looking for…"
          aria-label="Message Ember, the Hearth concierge"
          className="max-h-32 min-h-[44px] flex-1 resize-none rounded-xl border border-border bg-surface-muted px-3.5 py-2.5 text-small text-text placeholder:text-n-400 transition-colors focus-visible:border-accent-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong/40 disabled:opacity-60"
        />
        <button
          type="submit"
          data-testid="agent-chat-send"
          aria-label="Send message"
          disabled={busy || draft.trim().length === 0}
          className="grid h-11 w-11 flex-none place-items-center rounded-xl bg-accent text-n-900 transition-colors hover:bg-accent-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:cursor-not-allowed disabled:opacity-50"
        >
          <SendIcon />
        </button>
      </form>
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (text: string) => void }): JSX.Element {
  return (
    <div className="flex flex-col gap-3.5">
      <div
        data-testid="agent-message-assistant"
        className="max-w-[88%] self-start rounded-[14px_14px_14px_4px] bg-accent-tint px-3.5 py-3 text-small leading-relaxed text-text"
      >
        <span className="font-medium">Welcome in. I’m Ember.</span>
        <br />
        Tell me what you’re furnishing, gifting, or mending and I’ll recommend with reasons, grounded in the live catalogue.
      </div>
      <div className="flex flex-col gap-2">
        {STARTERS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onPick(s)}
            className="self-start rounded-full border border-border bg-surface px-3.5 py-1.5 text-left text-caption text-text-muted transition-colors hover:border-accent-strong/60 hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

function TurnView({
  turn,
  onNavigate,
}: {
  turn: Turn;
  onNavigate?: () => void;
}): JSX.Element {
  if (turn.role === "user") {
    return (
      <div
        data-testid="agent-message-user"
        className="max-w-[88%] self-end rounded-[14px_14px_4px_14px] bg-brand-tint px-3.5 py-2.5 text-small leading-relaxed text-text"
      >
        {turn.text}
      </div>
    );
  }
  return <AssistantTurnView turn={turn} onNavigate={onNavigate} />;
}

function AssistantTurnView({
  turn,
  onNavigate,
}: {
  turn: AssistantTurn;
  onNavigate?: () => void;
}): JSX.Element {
  const showThinking = turn.phase === "thinking";

  return (
    <div className="flex flex-col gap-2.5 self-start">
      {turn.text.length > 0 ? (
        <div
          data-testid="agent-message-assistant"
          className="max-w-[88%] rounded-[14px_14px_14px_4px] bg-accent-tint px-3.5 py-3 text-small leading-relaxed text-text"
        >
          {turn.text}
          {turn.phase === "streaming" ? (
            <span
              aria-hidden="true"
              className="ml-0.5 inline-block h-3.5 w-[2px] translate-y-0.5 animate-pulse bg-accent-text motion-reduce:animate-none"
            />
          ) : null}
        </div>
      ) : null}

      {/* Thinking presence — aria-live, static under reduced motion. */}
      {showThinking ? (
        <div
          data-testid="agent-thinking-indicator"
          aria-live="polite"
          className="inline-flex items-center gap-2 self-start text-caption font-medium text-accent-text"
        >
          <span>Ember is thinking</span>
          <span className="inline-flex gap-1" aria-hidden="true">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="h-1 w-1 rounded-full bg-accent-text/70 motion-safe:animate-bounce motion-reduce:animate-none"
                style={{ animationDelay: `${i * 120}ms` }}
              />
            ))}
          </span>
        </div>
      ) : null}

      {/* Citations — may arrive mid-stream. */}
      {turn.citations.length > 0 ? (
        <div className="flex max-w-[88%] flex-wrap gap-1.5">
          {turn.citations.map((c, i) => (
            <span
              key={`${c.source_id}-${c.chunk_index}-${i}`}
              data-testid="agent-citation"
              title={c.snippet}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-1 text-caption text-text-muted"
            >
              <CitationIcon />
              <span className="capitalize">{c.source_type}</span>
              <span aria-hidden="true">·</span>
              <span className="max-w-[16ch] truncate">{c.snippet}</span>
            </span>
          ))}
        </div>
      ) : null}

      {/* Clarify prompt — ambiguous query. */}
      {turn.clarify ? (
        <div
          data-testid="agent-clarify-prompt"
          className="max-w-[88%] rounded-[12px] border border-dashed border-accent-strong/50 bg-accent-tint/50 px-3.5 py-2.5 text-small leading-relaxed text-text"
        >
          {turn.clarify}
        </div>
      ) : null}

      {/* Refusal notice — out-of-scope / out-of-policy. */}
      {turn.refusal ? (
        <div
          data-testid="agent-refusal-notice"
          role="note"
          className="max-w-[88%] rounded-[12px] border border-warning/40 bg-warning-tint/60 px-3.5 py-2.5 text-small leading-relaxed text-[#7a560f]"
        >
          <span className="font-semibold">One honest note: </span>
          {turn.refusal}
        </div>
      ) : null}

      {/* Recommendation cards — the grounded generative UI. */}
      {turn.recommendations.length > 0 ? (
        <div className="flex max-w-full flex-col gap-2.5">
          {turn.recommendations.map((rec) => (
            <RecommendationCard key={rec.product_id} rec={rec} onNavigate={onNavigate} />
          ))}
        </div>
      ) : null}

      {/* Stream-level error — terminal. */}
      {turn.error ? (
        <div
          role="alert"
          className="max-w-[88%] rounded-[12px] border border-error/40 bg-error-tint/60 px-3.5 py-2.5 text-small leading-relaxed text-[#8a2f24]"
        >
          {turn.error.message}
        </div>
      ) : null}
    </div>
  );
}
