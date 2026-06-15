import { NextResponse } from "next/server";
import type { CartItemAdd, CartOut, Envelope } from "@/lib/api-types";
import { MOCK_PRODUCTS } from "@/lib/mock/catalog";

/**
 * MOCK `POST /cart/items` → `CartOut` (201). Lets the product page prove the
 * add-to-cart + "Added to cart" confirmation flow before the live cart service
 * (on `integration/agents`/backend) is wired. The optimistic UI updates first;
 * this confirms. At the W3 gate this handler proxies the contract `/cart/items`
 * with the httpOnly session token attached server-side.
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

  const variant = MOCK_PRODUCTS.flatMap((p) =>
    p.variants.map((v) => ({ product: p, variant: v })),
  ).find((x) => x.variant.id === body.variant_id);

  if (!variant) {
    return NextResponse.json(
      { error: { code: "not_found", message: "That option no longer exists.", details: null } },
      { status: 404 },
    );
  }

  if (variant.variant.stock === "out_of_stock") {
    return NextResponse.json(
      { error: { code: "out_of_stock", message: "That option just sold out.", details: null } },
      { status: 409 },
    );
  }

  const qty = Math.max(1, Math.floor(body.quantity || 1));
  const cart: CartOut = {
    id: "cart_mock",
    lines: [
      {
        id: `line_${variant.variant.id}`,
        variant_id: variant.variant.id,
        title: `${variant.product.title} · ${variant.variant.option_value}`,
        quantity: qty,
        unit_price_cents: variant.product.price_cents,
      },
    ],
    subtotal_cents: variant.product.price_cents * qty,
    currency: variant.product.currency,
  };

  const envelope: Envelope<CartOut> = { data: cart, meta: null };
  return NextResponse.json(envelope, { status: 201 });
}
