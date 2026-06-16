import { NextResponse } from "next/server";
import type { Envelope, PaymentConfirmRequest, PaymentOut } from "@/lib/api-types";
import { confirmPayment } from "@/lib/mock/orders";

/**
 * MOCK `POST /orders/{id}/payment-confirm` → `PaymentOut` (200) — step two of the
 * two-step test-mode payment. The decline is the CONTRACT switch, not an env flag:
 * `outcome="failed"` → `402 payment_declined`, the payment row lands `failed`, and
 * the order STAYS `placed` (unpaid) so the UI can offer a retry. `outcome="captured"`
 * (default) → success → the order advances to `packed`.
 */
export async function POST(
  request: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await ctx.params;
  let body: PaymentConfirmRequest;
  try {
    body = (await request.json()) as PaymentConfirmRequest;
  } catch {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Invalid request body.", details: null } },
      { status: 422 },
    );
  }

  const result = confirmPayment(id, body);
  if (!result) {
    return NextResponse.json(
      { error: { code: "not_found", message: "We couldn't find that payment.", details: null } },
      { status: 404 },
    );
  }

  if (result.declined) {
    return NextResponse.json(
      {
        error: {
          code: "payment_declined",
          message: "Your card was declined. No charge was made — you can try a different card.",
          details: null,
        },
      },
      { status: 402 },
    );
  }

  const envelope: Envelope<PaymentOut> = { data: result.payment, meta: null };
  return NextResponse.json(envelope);
}
