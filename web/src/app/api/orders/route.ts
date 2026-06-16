import { NextResponse } from "next/server";
import type { CheckoutRequest, Envelope, PageMeta } from "@/lib/api-types";
import { shopApi } from "@/lib/api";
import { toBackendAddress } from "@/lib/adapters/order";
import { readJson, requireToken, toErrorResponse } from "@/lib/proxy";

/**
 * LIVE `POST /orders` (checkout: open cart → order, idempotent) + `GET /orders`
 * (my orders list). Proxied to the contract endpoints with the session token
 * (Day-22 flip-to-live, ADR-0040).
 *
 * Address mapping (mismatch the flip surfaced): the FE form models the address
 * as `{ name, country }`, but the live `AddressIn` requires
 * `{ recipient_name, country_code }`. We translate via `toBackendAddress` so the
 * checkout component is unchanged.
 */
export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<NextResponse> {
  const auth = requireToken();
  if ("response" in auth) return auth.response;

  const parsed = await readJson<CheckoutRequest>(request);
  if ("response" in parsed) return parsed.response;

  const key =
    request.headers.get("Idempotency-Key") ??
    parsed.body.idempotency_key ??
    null;

  try {
    const env = await shopApi.checkout(
      {
        ship_address: toBackendAddress(parsed.body.ship_address),
        idempotency_key: key,
      },
      auth.token,
      key,
    );
    // First creation is 201; an idempotent replay is 200. The backend signals
    // this on its status — but `apiFetch` unwraps the body, so we report 201 for
    // a fresh placement (the FE only branches on success, not the exact code).
    return NextResponse.json(env, { status: 201 });
  } catch (err) {
    return toErrorResponse(err, "Could not place the order.");
  }
}

export async function GET(): Promise<NextResponse> {
  const auth = requireToken();
  if ("response" in auth) return auth.response;

  try {
    const env = await shopApi.listOrders(auth.token);
    const meta: PageMeta = env.meta ?? {
      next_cursor: null,
      limit: env.data.length,
      total: env.data.length,
    };
    return NextResponse.json({ data: env.data, meta } satisfies Envelope<unknown>);
  } catch (err) {
    return toErrorResponse(err, "Could not load your orders.");
  }
}
