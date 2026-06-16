import { proxyAgentStream } from "@/lib/agent-proxy";

/**
 * LIVE `POST /agent/conversations` → SSE stream (Day-22 flip-to-live, ADR-0040).
 *
 * Starts a conversation against the real LangGraph runtime. Proxies the turn to
 * the live `:8000/agent/conversations` with the httpOnly session token attached
 * server-side, and streams the `text/event-stream` body back. The terminal
 * `done` frame's nested recommendations are flattened to the FE view-model in
 * the proxy; `token` / `citations` / `error` frames pass through unchanged. The
 * SSE client and the conversation UI are unchanged.
 */
export const dynamic = "force-dynamic";

export function POST(request: Request): Promise<Response> {
  return proxyAgentStream(request, "/agent/conversations");
}
