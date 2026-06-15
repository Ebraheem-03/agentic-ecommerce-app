import type {
  Citation,
  CitationsEvent,
  ConversationStartRequest,
  DoneEvent,
  ErrorBody,
  MessageRequest,
  StreamError,
  TokenEvent,
} from "@/lib/api-types";

/**
 * Hearth agent (Ember) SSE client.
 *
 * Speaks the LOCKED contract event protocol (ADR-0021, contract-v0.md §"Agent
 * SSE event protocol"): the assistant turn arrives as ordered `text/event-stream`
 * frames — `token` (0..n) → `citations` (0..1) → `done` (terminal), or `error`
 * (terminal). Each `data:` payload is JSON of a typed model.
 *
 * This module is transport-only: it turns the raw byte stream into a typed async
 * sequence of `AgentFrame`s via callbacks. It does NOT know about React. The
 * panel store drives the streaming state machine off these callbacks.
 *
 * The endpoint base is env-driven (`AGENT_STREAM_PATH`): today it points at our
 * same-origin MOCK route handlers under `/api/agent/*` (the backend SSE runtime
 * lives on `integration/agents`, not on this line). Flipping to the live backend
 * at the W3 gate is a config change — set `NEXT_PUBLIC_AGENT_STREAM_BASE` to the
 * API origin and the same parser consumes the real stream unchanged.
 */

/** Where the browser POSTs to open/continue a stream. Defaults to our mock. */
export const AGENT_STREAM_BASE =
  process.env.NEXT_PUBLIC_AGENT_STREAM_BASE?.replace(/\/$/, "") ?? "/api/agent";

export type AgentFrame =
  | { type: "token"; data: TokenEvent }
  | { type: "citations"; data: CitationsEvent }
  | { type: "done"; data: DoneEvent }
  | { type: "error"; data: StreamError };

export interface AgentStreamHandlers {
  onToken?: (delta: string) => void;
  onCitations?: (citations: Citation[]) => void;
  onDone?: (done: DoneEvent) => void;
  /** Terminal error — either a stream `error` frame or a transport failure. */
  onError?: (error: ErrorBody) => void;
}

/** Build the canonical error body for a transport-level (non-frame) failure. */
function transportError(message: string): ErrorBody {
  return { code: "internal_error", message, details: null };
}

/**
 * Minimal SSE frame parser. The wire is blank-line-delimited records, each with
 * an `event:` line and one-or-more `data:` lines. We only need single-line data
 * payloads (the contract emits compact JSON), but we concatenate multi-line data
 * with `\n` per the SSE spec to stay robust.
 */
function parseRecord(raw: string): AgentFrame | null {
  let event = "message";
  const dataLines: string[] = [];

  for (const line of raw.split("\n")) {
    if (line.startsWith(":")) continue; // comment / heartbeat
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).replace(/^ /, ""));
    }
  }

  if (dataLines.length === 0) return null;
  const dataText = dataLines.join("\n");

  let payload: unknown;
  try {
    payload = JSON.parse(dataText);
  } catch {
    return null;
  }

  switch (event) {
    case "token":
      return { type: "token", data: payload as TokenEvent };
    case "citations":
      return { type: "citations", data: payload as CitationsEvent };
    case "done":
      return { type: "done", data: payload as DoneEvent };
    case "error":
      return { type: "error", data: payload as StreamError };
    default:
      return null;
  }
}

interface StreamArgs {
  /** Conversation to continue, or null to start a new one. */
  conversationId: string | null;
  body: ConversationStartRequest | MessageRequest;
  /** Idempotency key for follow-up messages (contract requires it). */
  idempotencyKey?: string;
  handlers: AgentStreamHandlers;
  signal?: AbortSignal;
}

/**
 * Open the assistant turn and dispatch typed frames to `handlers` in arrival
 * order. Resolves when the stream closes (after `done`/`error` or EOF). Never
 * throws for an in-band error frame — it routes to `onError`; only a genuine
 * abort rejects (callers can ignore `AbortError`).
 */
export async function streamAgentTurn({
  conversationId,
  body,
  idempotencyKey,
  handlers,
  signal,
}: StreamArgs): Promise<void> {
  const path =
    conversationId === null
      ? `${AGENT_STREAM_BASE}/conversations`
      : `${AGENT_STREAM_BASE}/conversations/${conversationId}/messages`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;

  let res: Response;
  try {
    res = await fetch(path, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if (signal?.aborted) return;
    handlers.onError?.(
      transportError(
        err instanceof Error ? err.message : "Could not reach the assistant.",
      ),
    );
    return;
  }

  if (!res.ok || !res.body) {
    // A non-2xx may still carry the canonical error envelope as JSON.
    let body: ErrorBody | null = null;
    try {
      const json = (await res.json()) as { error?: ErrorBody };
      body = json.error ?? null;
    } catch {
      body = null;
    }
    handlers.onError?.(
      body ?? transportError(`The assistant is unavailable (${res.status}).`),
    );
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const flush = (record: string): void => {
    const frame = parseRecord(record);
    if (!frame) return;
    switch (frame.type) {
      case "token":
        handlers.onToken?.(frame.data.delta);
        break;
      case "citations":
        handlers.onCitations?.(frame.data.citations);
        break;
      case "done":
        handlers.onDone?.(frame.data);
        break;
      case "error":
        handlers.onError?.(frame.data.error);
        break;
    }
  };

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Records are separated by a blank line (\n\n).
      let sep = buffer.indexOf("\n\n");
      while (sep !== -1) {
        const record = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        if (record.trim()) flush(record);
        sep = buffer.indexOf("\n\n");
      }
    }
    // Trailing record without a final blank line.
    if (buffer.trim()) flush(buffer);
  } catch (err) {
    if (signal?.aborted) return;
    handlers.onError?.(
      transportError(
        err instanceof Error ? err.message : "The assistant stream dropped.",
      ),
    );
  }
}
