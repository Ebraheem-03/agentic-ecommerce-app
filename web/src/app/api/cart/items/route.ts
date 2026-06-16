import { NextResponse } from "next/server";
import type { CartItemAdd, CartOut, Envelope } from "@/lib/api-types";
import { addLine, variantOutOfStock } from "@/lib/mock/cart";

/**
 * MOCK `POST /cart/items` → `CartOut` (201). Add/increment a variant in the open
 * cart. Mutates the shared mock cart store (ADR-0037); the optimistic UI updates
 * first and this confirms. At the W3 gate this handler proxies the contract
 * `/cart/items` with the httpOnly session token attached server-side.
 *
 * Deterministic out-of-stock path for QA: adding the OOS Ember bowl variant
 * (`var_bowl_ember`) returns `409 out_of_stock`.
 */
export async function POST(request: Request): Promise<NextResponse> {
  let body: CartItemAdd;
  try {
    body = (await request.json()) as CartItemAdd;
  } catch {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Invalid request body.", details: null } },
      { status: 422 },
    );
  }

  if (variantOutOfStock(body.variant_id)) {
    return NextResponse.json(
      { error: { code: "out_of_stock", message: "That option just sold out.", details: null } },
      { status: 409 },
    );
  }

  const qty = Math.max(1, Math.floor(body.qty || 1));
  const cart = addLine(body.variant_id, qty);
  if (!cart) {
    return NextResponse.json(
      { error: { code: "not_found", message: "That option no longer exists.", details: null } },
      { status: 404 },
    );
  }

  const envelope: Envelope<CartOut> = { data: cart, meta: null };
  return NextResponse.json(envelope, { status: 201 });
}
