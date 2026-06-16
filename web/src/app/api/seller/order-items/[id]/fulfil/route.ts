import { NextResponse } from "next/server";
import type { Envelope, FulfilRequest, SellerFulfilItem } from "@/lib/api-types";
import { fulfilItem } from "@/lib/mock/seller";

// MOCK until the returns/seller backend lands (Day-22 scope call; ADR-0040).
/**
 * MOCK `PATCH /seller/order-items/{id}/fulfil` → the updated line (200) — mark a
 * line fulfilled/cancelled. Mutates the shared mock seller store (ADR-0037). At
 * the W3 gate this proxies the contract endpoint (which returns `OrderSummary`).
 */
export async function PATCH(
  request: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await ctx.params;
  let body: FulfilRequest;
  try {
    body = (await request.json()) as FulfilRequest;
  } catch {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Invalid request body.", details: null } },
      { status: 422 },
    );
  }
  const item = fulfilItem(id, body.fulfil_status);
  if (!item) {
    return NextResponse.json(
      { error: { code: "not_found", message: "That order line no longer exists.", details: null } },
      { status: 404 },
    );
  }
  const envelope: Envelope<SellerFulfilItem> = { data: item, meta: null };
  return NextResponse.json(envelope);
}
