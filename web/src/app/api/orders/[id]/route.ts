import { NextResponse } from "next/server";
import type { Envelope, OrderDetail } from "@/lib/api-types";
import { getOrder } from "@/lib/mock/orders";

/**
 * MOCK `GET /orders/{id}` → `OrderDetail` (200) — order detail + the status
 * timeline source + per-item snapshots + payment status. Reads the shared mock
 * orders store (ADR-0037). At the W3 gate this proxies the contract `/orders/{id}`.
 */
export async function GET(
  _request: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await ctx.params;
  const order = getOrder(id);
  if (!order) {
    return NextResponse.json(
      { error: { code: "not_found", message: "We couldn't find that order.", details: null } },
      { status: 404 },
    );
  }
  const envelope: Envelope<OrderDetail> = { data: order, meta: null };
  return NextResponse.json(envelope);
}
