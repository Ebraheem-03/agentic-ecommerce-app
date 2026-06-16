import { proxyAgentStream } from "@/lib/agent-proxy";

/**
 * LIVE `POST /agent/conversations/{id}/messages` → SSE stream (Day-22 flip,
 * ADR-0040). Follow-up turns in an existing conversation, including the live
 * checkout-approval interrupt path (interrupt → resume on Approve). Proxies to
 * the live `:8000/agent/conversations/{id}/messages` with the session token +
 * the `Idempotency-Key` header passed through; `done`-frame recommendations are
 * flattened in the proxy, all other frames pass through unchanged.
 */
export const dynamic = "force-dynamic";

export async function POST(
  request: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await ctx.params;
  return proxyAgentStream(request, `/agent/conversations/${id}/messages`);
}
