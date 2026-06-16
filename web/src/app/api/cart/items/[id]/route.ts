import { NextResponse } from "next/server";
import type { CartItemUpdate, CartOut, Envelope } from "@/lib/api-types";
import { removeLine, setLineQty } from "@/lib/mock/cart";

/**
 * MOCK `PATCH /cart/items/{id}` (set absolute qty>0) + `DELETE /cart/items/{id}`
 * (remove the line) → `CartOut` (200). Mutates the shared mock cart store
 * (ADR-0037). At the W3 gate these proxy the contract `/cart/items/{id}`.
 */

interface Ctx {
  params: Promise<{ id: string }>;
}

const notFound = (): NextResponse =>
  NextResponse.json(
    { error: { code: "not_found", message: "That cart line no longer exists.", details: null } },
    { status: 404 },
  );

export async function PATCH(request: Request, ctx: Ctx): Promise<NextResponse> {
  const { id } = await ctx.params;
  let body: CartItemUpdate;
  try {
    body = (await request.json()) as CartItemUpdate;
  } catch {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Invalid request body.", details: null } },
      { status: 422 },
    );
  }
  if (!Number.isFinite(body.qty) || body.qty < 1) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Quantity must be at least 1.", details: null } },
      { status: 422 },
    );
  }
  const cart = setLineQty(id, body.qty);
  if (!cart) return notFound();
  const envelope: Envelope<CartOut> = { data: cart, meta: null };
  return NextResponse.json(envelope);
}

export async function DELETE(_request: Request, ctx: Ctx): Promise<NextResponse> {
  const { id } = await ctx.params;
  const cart = removeLine(id);
  if (!cart) return notFound();
  const envelope: Envelope<CartOut> = { data: cart, meta: null };
  return NextResponse.json(envelope);
}
