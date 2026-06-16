import { NextResponse } from "next/server";
import type { Envelope, PaymentIntentOut } from "@/lib/api-types";
import { createIntent } from "@/lib/mock/orders";

/**
 * MOCK `POST /orders/{id}/payment-intent` → `PaymentIntentOut` (201) — step one
 * of the two-step test-mode payment. No real PSP; returns a mock client secret +
 * a pending payment row on the order (ADR-0037). Idempotent per order. At the W3
 * gate this proxies the contract endpoint with the `Idempotency-Key` header.
 */
export async function POST(
  _request: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await ctx.params;
  const intent = createIntent(id);
  if (!intent) {
    return NextResponse.json(
      { error: { code: "not_found", message: "We couldn't find that order.", details: null } },
      { status: 404 },
    );
  }
  const envelope: Envelope<PaymentIntentOut> = { data: intent, meta: null };
  return NextResponse.json(envelope, { status: 201 });
}
