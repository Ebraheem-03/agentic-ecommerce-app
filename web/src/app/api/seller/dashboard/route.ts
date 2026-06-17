import { NextResponse } from "next/server";
import type { Envelope, NudgeOut, OrderSummary, SellerDashboard } from "@/lib/api-types";
import { apiFetch } from "@/lib/api";
import { requireToken, toErrorResponse } from "@/lib/proxy";
import {
  toSellerDashboard,
  type SellerOrderDetail,
} from "@/lib/adapters/seller";

/**
 * LIVE `GET /seller/dashboard` (Day-24 flip-to-live, ADR-0040; fulfil-table
 * wiring follow-up, ADR-0045).
 *
 * There is NO `/seller/dashboard` aggregate on the backend — this is an FE-only
 * convenience the proxy composes server-side by fanning out to the live
 * endpoints (so the browser still makes one same-origin call):
 *   - `GET /seller/orders`       → orders the seller must fulfil (`OrderSummary[]`),
 *   - `GET /seller/orders/{id}`  → that order's seller-scoped LINES
 *                                  (`SellerOrderDetail`, own-store lines only),
 *   - `GET /seller/nudges`       → agent-generated merchandising nudges.
 *
 * The per-line fulfil table is now backed live: for each summary we fetch its
 * seller-scoped detail CONCURRENTLY (Promise.all — the fan-out is N+1 by shape
 * but seed data is tiny), then flatten `items[]` → `SellerFulfilItem[]`. Each
 * line's `id` is the `order_item_id` the fulfil PATCH targets. Mapping + the
 * wire-casing note live in `@/lib/adapters/seller`.
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

    const orders = ordersEnv.data ?? [];

    // Fan out per order for its seller-scoped lines — concurrently, not in series.
    const detailEnvs = await Promise.all(
      orders.map((o) =>
        apiFetch<SellerOrderDetail>(`/seller/orders/${o.id}`, {
          token: auth.token,
          init: { cache: "no-store" },
        }),
      ),
    );
    const orderDetails = detailEnvs
      .map((env) => env.data)
      .filter((d): d is SellerOrderDetail => d != null);

    const dashboard = toSellerDashboard(
      orders,
      orderDetails,
      nudgesEnv.data ?? [],
    );
    const envelope: Envelope<SellerDashboard> = { data: dashboard, meta: null };
    return NextResponse.json(envelope);
  } catch (err) {
    return toErrorResponse(err, "Could not load the dashboard.");
  }
}
