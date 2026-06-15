"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useReducer,
  useRef,
} from "react";
import type { ReactNode } from "react";
import type {
  AgentRecommendation,
  Citation,
  ConversationStartRequest,
  DoneEvent,
  ErrorBody,
} from "@/lib/api-types";
import { streamAgentTurn } from "@/lib/agent-stream";

/**
 * Ember conversation store — owns the streaming state machine for the docked
 * panel. Lives at the `(shop)` layout level so the conversation PERSISTS across
 * home / search / product navigation (ADR-0036). Drives the SSE client
 * (`streamAgentTurn`) over the mock stream and reduces frames into renderable
 * turns.
 *
 * State machine per turn:
 *   idle ──submit──▶ thinking ──first token──▶ streaming
 *     thinking/streaming ──citations──▶ (attach to active turn)
 *     streaming ──done──▶ idle  (recommendations / clarify / refusal attached)
 *     any ──error──▶ idle  (error attached to active turn)
 *
 * The `phase` is what the UI reads to show `agent-thinking-indicator`, the
 * streaming caret, and the disabled/enabled composer.
 */

export type TurnPhase = "thinking" | "streaming" | "done" | "error";

export interface AssistantTurn {
  id: string;
  role: "assistant";
  text: string;
  phase: TurnPhase;
  citations: Citation[];
  recommendations: AgentRecommendation[];
  /** Disambiguation copy → `agent-clarify-prompt`. */
  clarify: string | null;
  /** Out-of-scope copy → `agent-refusal-notice`. */
  refusal: string | null;
  error: ErrorBody | null;
}

export interface UserTurn {
  id: string;
  role: "user";
  text: string;
}

export type Turn = AssistantTurn | UserTurn;

interface AgentState {
  conversationId: string | null;
  turns: Turn[];
  /** True while a turn is mid-stream (thinking or streaming). */
  busy: boolean;
}

type Action =
  | { type: "user_submit"; userId: string; assistantId: string; text: string }
  | { type: "token"; id: string; delta: string }
  | { type: "citations"; id: string; citations: Citation[] }
  | { type: "done"; id: string; done: DoneEvent }
  | { type: "error"; id: string; error: ErrorBody };

function reduce(state: AgentState, action: Action): AgentState {
  switch (action.type) {
    case "user_submit": {
      const user: UserTurn = { id: action.userId, role: "user", text: action.text };
      const assistant: AssistantTurn = {
        id: action.assistantId,
        role: "assistant",
        text: "",
        phase: "thinking",
        citations: [],
        recommendations: [],
        clarify: null,
        refusal: null,
        error: null,
      };
      return { ...state, busy: true, turns: [...state.turns, user, assistant] };
    }
    case "token":
      return {
        ...state,
        turns: state.turns.map((t) =>
          t.id === action.id && t.role === "assistant"
            ? { ...t, text: t.text + action.delta, phase: "streaming" }
            : t,
        ),
      };
    case "citations":
      return {
        ...state,
        turns: state.turns.map((t) =>
          t.id === action.id && t.role === "assistant"
            ? { ...t, citations: action.citations }
            : t,
        ),
      };
    case "done":
      return {
        ...state,
        busy: false,
        conversationId: action.done.conversation_id ?? state.conversationId,
        turns: state.turns.map((t) =>
          t.id === action.id && t.role === "assistant"
            ? {
                ...t,
                phase: "done",
                recommendations: action.done.recommendations ?? [],
                clarify: action.done.clarify ?? null,
                refusal: action.done.refusal ?? null,
              }
            : t,
        ),
      };
    case "error":
      return {
        ...state,
        busy: false,
        turns: state.turns.map((t) =>
          t.id === action.id && t.role === "assistant"
            ? { ...t, phase: "error", error: action.error }
            : t,
        ),
      };
    default:
      return state;
  }
}

export interface AgentContextValue extends AgentState {
  send: (text: string, context?: ConversationStartRequest["context"]) => void;
}

const AgentContext = createContext<AgentContextValue | null>(null);

let seq = 0;
const nextId = (prefix: string): string => `${prefix}_${Date.now()}_${seq++}`;

export function AgentProvider({ children }: { children: ReactNode }): JSX.Element {
  const [state, dispatch] = useReducer(reduce, {
    conversationId: null,
    turns: [],
    busy: false,
  });
  const busyRef = useRef(false);
  const convRef = useRef<string | null>(null);
  busyRef.current = state.busy;
  convRef.current = state.conversationId;

  const send = useCallback(
    (text: string, context?: ConversationStartRequest["context"]) => {
      const trimmed = text.trim();
      if (!trimmed || busyRef.current) return;

      const assistantId = nextId("a");
      dispatch({
        type: "user_submit",
        userId: nextId("u"),
        assistantId,
        text: trimmed,
      });

      const conversationId = convRef.current;
      void streamAgentTurn({
        conversationId,
        body:
          conversationId === null
            ? { surface: "buyer", message: trimmed, context: context ?? null }
            : { message: trimmed, context: context ?? null },
        idempotencyKey: conversationId === null ? undefined : nextId("idem"),
        handlers: {
          onToken: (delta) => dispatch({ type: "token", id: assistantId, delta }),
          onCitations: (citations) =>
            dispatch({ type: "citations", id: assistantId, citations }),
          onDone: (done) => dispatch({ type: "done", id: assistantId, done }),
          onError: (error) => dispatch({ type: "error", id: assistantId, error }),
        },
      });
    },
    [],
  );

  const value = useMemo<AgentContextValue>(
    () => ({ ...state, send }),
    [state, send],
  );

  return <AgentContext.Provider value={value}>{children}</AgentContext.Provider>;
}

export function useAgent(): AgentContextValue {
  const ctx = useContext(AgentContext);
  if (!ctx) throw new Error("useAgent must be used within an AgentProvider");
  return ctx;
}
