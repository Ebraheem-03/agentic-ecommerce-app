import { NextResponse } from "next/server";
import type { Envelope, NudgeOut, OrderSummary, SellerDashboard } from "@/lib/api-types";
import { apiFetch } from "@/lib/api";
import { requireToken, toErrorResponse } from "@/lib/proxy";
import { toSellerDashboard } from "@/lib/adapters/seller";

/**
 * LIVE `GET /seller/dashboard` (Day-24 flip-to-live, ADR-0040).
 *
 * There is NO `/seller/dashboard` aggregate on the backend — this is an FE-only
 * convenience the proxy composes server-side by fanning out to the live
 * endpoints (so the browser still makes one same-origin call):
 *   - `GET /seller/orders`  → orders the seller must fulfil (`OrderSummary[]`),
 *   - `GET /seller/nudges`  → agent-generated merchandising nudges.
 *
 * KNOWN BACKEND GAP (flagged for Atlas/Orion): the per-line fulfil table has no
 * live source — `OrderSummary` carries no items and `GET /orders/{id}` is
 * buyer-owner-scoped (404 for the seller). `order_items` and `listings` are left
 * empty; mapping + the full gap note live in `@/lib/adapters/seller`.
 */
export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse> {
  const auth = requireToken();
  if ("response" in auth) return auth.response;

  try {
    const [ordersEnv, nudgesEnv] = await Promise.all([
      apiFetch<OrderSummary[]>("/seller/orders", {
        token: auth.token,
        init: { cache: "no-store" },
      }),
      apiFetch<NudgeOut[]>("/seller/nudges", {
        token: auth.token,
        init: { cache: "no-store" },
      }),
    ]);

    const dashboard = toSellerDashboard(
      ordersEnv.data ?? [],
      nudgesEnv.data ?? [],
    );
    const envelope: Envelope<SellerDashboard> = { data: dashboard, meta: null };
    return NextResponse.json(envelope);
  } catch (err) {
    return toErrorResponse(err, "Could not load the dashboard.");
  }
}
