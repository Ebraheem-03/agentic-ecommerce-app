import { NextResponse } from "next/server";
import { shopApi } from "@/lib/api";
import { requireToken, toErrorResponse } from "@/lib/proxy";

/**
 * LIVE `POST /orders/{id}/payment-intent` → `PaymentIntentOut` (201) — step one
 * of the two-step test-mode payment. Proxied to the contract endpoint with the
 * session token + the `Idempotency-Key` header passed through (Day-22 flip,
 * ADR-0040).
 */
export async function POST(
  request: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const auth = requireToken();
  if ("response" in auth) return auth.response;
  const { id } = await ctx.params;
  const key = request.headers.get("Idempotency-Key");

  try {
    const env = await shopApi.paymentIntent(id, auth.token, key);
    return NextResponse.json(env, { status: 201 });
  } catch (err) {
    return toErrorResponse(err, "Could not start the payment.");
  }
}
