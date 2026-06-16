import { API_BASE_URL } from "@/lib/api";
import { getSessionToken } from "@/lib/session";
import { toAgentRecommendation } from "@/lib/adapters/catalog";
import type { BackendRecommendation } from "@/lib/adapters/catalog";

/**
 * Live agent SSE proxy (Day-22 flip-to-live, ADR-0040).
 *
 * The browser POSTs to our same-origin `/api/agent/*` handlers; this forwards the
 * turn to the live `:8000/agent/*` SSE runtime with the httpOnly session token
 * attached server-side, and streams the `text/event-stream` body straight back.
 *
 * ONE frame is rewritten in flight: the terminal `done` frame. The live
 * `DoneEvent.recommendations[]` are NESTED (`{ product: ProductSummary, reason }`)
 * but the FE `AgentStream`/`DoneEvent` expects FLAT `AgentRecommendation[]`
 * (`maker`, `price_cents`, `image_alt`, …). We parse each SSE record, map only
 * `event: done` payloads via `toAgentRecommendation`, and pass `token` /
 * `citations` / `error` records through untouched. This keeps the live
 * checkout-approval interrupt path (interrupt → resume) flowing unchanged —
 * those frames are not `done` frames and are forwarded verbatim.
 */

/** Map a single SSE record. Rewrites only the `done` frame; passes the rest. */
function mapRecord(record: string): string {
  // Find the event type and the data payload within this record.
  const lines = record.split("\n");
  let event = "message";
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).replace(/^ /, ""));
  }
  if (event !== "done" || dataLines.length === 0) return record;

  let payload: {
    recommendations?: BackendRecommendation[];
    [k: string]: unknown;
  };
  try {
    payload = JSON.parse(dataLines.join("\n"));
  } catch {
    return record; // not JSON we recognize — pass through verbatim
  }

  const recs = Array.isArray(payload.recommendations)
    ? payload.recommendations.map(toAgentRecommendation)
    : [];
  const mapped = { ...payload, recommendations: recs };
  return `event: done\ndata: ${JSON.stringify(mapped)}`;
}

/** A TransformStream that rewrites `done` frames in an SSE byte stream. */
function doneFrameTransformer(): TransformStream<Uint8Array, Uint8Array> {
  const decoder = new TextDecoder();
  const encoder = new TextEncoder();
  let buffer = "";

  return new TransformStream<Uint8Array, Uint8Array>({
    transform(chunk, controller) {
      buffer += decoder.decode(chunk, { stream: true });
      let sep = buffer.indexOf("\n\n");
      while (sep !== -1) {
        const record = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        controller.enqueue(encoder.encode(`${mapRecord(record)}\n\n`));
        sep = buffer.indexOf("\n\n");
      }
    },
    flush(controller) {
      if (buffer.trim()) {
        controller.enqueue(encoder.encode(mapRecord(buffer)));
      }
    },
  });
}

/**
 * Forward an agent turn to the live SSE runtime and stream the (done-mapped)
 * response back. `path` is the live sub-path, e.g. `/agent/conversations` or
 * `/agent/conversations/{id}/messages`.
 */
export async function proxyAgentStream(
  request: Request,
  path: string,
): Promise<Response> {
  const token = getSessionToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const idem = request.headers.get("Idempotency-Key");
  if (idem) headers["Idempotency-Key"] = idem;

  const rawBody = await request.text();

  const upstream = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers,
    body: rawBody,
    // @ts-expect-error — Node fetch streaming flag; harmless where unsupported.
    duplex: "half",
  });

  // A non-2xx may carry the canonical error envelope (JSON) rather than a stream.
  if (!upstream.ok || !upstream.body) {
    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: {
        "Content-Type":
          upstream.headers.get("Content-Type") ?? "application/json",
      },
    });
  }

  const transformed = upstream.body.pipeThrough(doneFrameTransformer());

  return new Response(transformed, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
