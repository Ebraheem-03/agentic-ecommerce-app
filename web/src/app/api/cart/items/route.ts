import { NextResponse } from "next/server";
import type { CartItemAdd } from "@/lib/api-types";
import { shopApi } from "@/lib/api";
import { readJson, requireToken, toErrorResponse } from "@/lib/proxy";

/**
 * LIVE `POST /cart/items` → `CartOut` (201). Add/increment a variant in the open
 * cart, proxied to the contract endpoint with the session token (Day-22 flip,
 * ADR-0040). The optimistic UI updates first; this confirms. The backend owns
 * the `out_of_stock` (409) decision now — we forward its error envelope as-is.
 */
export async function POST(request: Request): Promise<NextResponse> {
  const auth = requireToken();
  if ("response" in auth) return auth.response;

  const parsed = await readJson<CartItemAdd>(request);
  if ("response" in parsed) return parsed.response;

  try {
    const env = await shopApi.addCartItem(parsed.body, auth.token);
    return NextResponse.json(env, { status: 201 });
  } catch (err) {
    return toErrorResponse(err, "Could not add to cart.");
  }
}
