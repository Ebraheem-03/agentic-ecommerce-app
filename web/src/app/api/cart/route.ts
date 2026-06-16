import { NextResponse } from "next/server";
import type { Envelope } from "@/lib/api-types";
import { shopApi } from "@/lib/api";
import { requireToken, toErrorResponse } from "@/lib/proxy";

/**
 * LIVE `GET /cart` → `CartOut` (200). Proxies the contract `/cart` with the
 * httpOnly session token attached server-side (Day-22 flip-to-live, ADR-0040).
 * `CartOut` already speaks `*_minor`/`qty`, so no adapter mapping is needed.
 */
export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse> {
  const auth = requireToken();
  if ("response" in auth) return auth.response;

  try {
    const env = await shopApi.getCart(auth.token);
    return NextResponse.json(env satisfies Envelope<unknown>);
  } catch (err) {
    return toErrorResponse(err, "Could not load your cart.");
  }
}
