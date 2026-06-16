import { NextResponse } from "next/server";
import type { CartItemUpdate } from "@/lib/api-types";
import { shopApi } from "@/lib/api";
import { readJson, requireToken, toErrorResponse } from "@/lib/proxy";

/**
 * LIVE `PATCH /cart/items/{id}` (set absolute qty>0) + `DELETE /cart/items/{id}`
 * (remove the line) → `CartOut` (200). Proxies the contract endpoints with the
 * session token (Day-22 flip-to-live, ADR-0040).
 */

interface Ctx {
  params: Promise<{ id: string }>;
}

export async function PATCH(request: Request, ctx: Ctx): Promise<NextResponse> {
  const auth = requireToken();
  if ("response" in auth) return auth.response;
  const { id } = await ctx.params;

  const parsed = await readJson<CartItemUpdate>(request);
  if ("response" in parsed) return parsed.response;

  try {
    const env = await shopApi.updateCartItem(id, parsed.body, auth.token);
    return NextResponse.json(env);
  } catch (err) {
    return toErrorResponse(err, "Could not update the cart.");
  }
}

export async function DELETE(
  _request: Request,
  ctx: Ctx,
): Promise<NextResponse> {
  const auth = requireToken();
  if ("response" in auth) return auth.response;
  const { id } = await ctx.params;

  try {
    const env = await shopApi.removeCartItem(id, auth.token);
    return NextResponse.json(env);
  } catch (err) {
    return toErrorResponse(err, "Could not remove that item.");
  }
}
