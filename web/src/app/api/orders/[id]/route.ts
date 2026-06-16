import { NextResponse } from "next/server";
import { shopApi } from "@/lib/api";
import { requireToken, toErrorResponse } from "@/lib/proxy";

/**
 * LIVE `GET /orders/{id}` → `OrderDetail` (200) — order detail + status timeline
 * source + per-item snapshots + payment status. Proxied to the contract endpoint
 * with the session token (Day-22 flip-to-live, ADR-0040). `OrderDetail` already
 * speaks `*_minor`, so no adapter mapping is needed; `return_eligible` is derived
 * client-side (returns is deferred today).
 */
export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const auth = requireToken();
  if ("response" in auth) return auth.response;
  const { id } = await ctx.params;

  try {
    const env = await shopApi.getOrder(id, auth.token);
    return NextResponse.json(env);
  } catch (err) {
    return toErrorResponse(err, "Could not load that order.");
  }
}
