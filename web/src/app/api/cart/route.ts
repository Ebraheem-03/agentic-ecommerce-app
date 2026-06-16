import { NextResponse } from "next/server";
import type { CartOut, Envelope } from "@/lib/api-types";
import { getCart, resetCart } from "@/lib/mock/cart";

/**
 * MOCK `GET /cart` → `CartOut` (200). Returns the (lazily-created) open cart from
 * the shared mock store (ADR-0037). At the W3 gate this proxies the contract
 * `/cart` with the httpOnly session token attached server-side.
 *
 * Deterministic cues for the [REVIEW] render + E2E:
 *  - `?reset=empty` → clears the cart to the empty state (`cart-empty-state`).
 *  - `?reset=seed`  → restores the two seed lines (a non-empty cold cart).
 */
export function GET(request: Request): NextResponse {
  const reset = new URL(request.url).searchParams.get("reset");
  let cart: CartOut;
  if (reset === "empty") cart = resetCart(true);
  else if (reset === "seed") cart = resetCart(false);
  else cart = getCart();

  const envelope: Envelope<CartOut> = { data: cart, meta: null };
  return NextResponse.json(envelope);
}
