import type { ScriptFrame } from "@/lib/mock/agent-scenarios";

/**
 * Serialise a scripted scenario into a `text/event-stream` Response body that
 * mirrors the locked wire format (contract-v0.md §"Agent SSE event protocol"):
 * each record is `event: <name>\ndata: <json>\n\n`. Frames are emitted with a
 * small delay between them so the client genuinely streams token-by-token (the
 * UI's thinking → streaming → done state machine is exercised for real). The
 * `delayMs` is collapsed to ~0 when `instant` is set, for fast deterministic
 * E2E runs that don't want to wait on wall-clock timing.
 */
export function scenarioToStream(
  frames: ScriptFrame[],
  { instant = false }: { instant?: boolean } = {},
): Response {
  const encoder = new TextEncoder();

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const write = (event: string, data: unknown): void => {
        const payload = JSON.stringify(data);
        controller.enqueue(encoder.encode(`event: ${event}\ndata: ${payload}\n\n`));
      };

      for (const frame of frames) {
        if (!instant && frame.delayMs > 0) {
          await new Promise((r) => setTimeout(r, frame.delayMs));
        }
        switch (frame.kind) {
          case "token":
            write("token", { delta: frame.delta });
            break;
          case "citations":
            write("citations", { citations: frame.citations });
            break;
          case "done":
            write("done", frame.done);
            break;
          case "error":
            write("error", { error: frame.error });
            break;
        }
      }
      controller.close();
    },
  });

  return new Response(stream, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}

/** Whether the request asks for an instant (no-delay) stream — `?instant=1`. */
export function wantsInstant(request: Request): boolean {
  const v = new URL(request.url).searchParams.get("instant");
  return v === "1" || v === "true";
}
