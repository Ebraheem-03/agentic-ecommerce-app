import { NextResponse } from "next/server";
import type { PaymentConfirmRequest } from "@/lib/api-types";
import { shopApi } from "@/lib/api";
import { readJson, requireToken, toErrorResponse } from "@/lib/proxy";

/**
 * LIVE `POST /orders/{id}/payment-confirm` → `PaymentOut` (200) — step two of the
 * two-step test-mode payment. Proxied to the contract endpoint with the session
 * token (Day-22 flip-to-live, ADR-0040). The decline is the CONTRACT switch
 * (`outcome="failed"` → `402 payment_declined`); the backend owns it and we
 * forward its error envelope as-is so the UI can offer a retry.
 */
export async function POST(
  request: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const auth = requireToken();
  if ("response" in auth) return auth.response;
  const { id } = await ctx.params;

  const parsed = await readJson<PaymentConfirmRequest>(request);
  if ("response" in parsed) return parsed.response;

  try {
    const env = await shopApi.paymentConfirm(id, parsed.body, auth.token);
    return NextResponse.json(env);
  } catch (err) {
    return toErrorResponse(err, "Could not confirm the payment.");
  }
}
