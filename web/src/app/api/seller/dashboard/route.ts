import { NextResponse } from "next/server";
import type {
  Envelope,
  NudgeOut,
  OrderSummary,
  SellerDashboard,
  SellerListing,
} from "@/lib/api-types";
import type { BackendProductDetail } from "@/lib/adapters/catalog";
import { apiFetch } from "@/lib/api";
import { requireToken, toErrorResponse } from "@/lib/proxy";
import {
  toListings,
  toSellerDashboard,
  type BackendStoreProduct,
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
 *
 * Store name + listings (Task 7): the backend has NO `GET /seller/store` and no
 * seller-scoped listings endpoint, but `GET /products?store_id=` IS store-
 * filterable and `GET /products/{id}` carries `store{id,name}`. So we resolve the
 * seller's own store WITHOUT a backend change: take a `product_id` the seller
 * owns from their nudges (grounded in their catalogue), fetch that product to
 * learn `store.id` + `store.name`, then list `GET /products?store_id=` for the
 * full inventory snapshot. A seller with NO nudges can't be resolved this way →
 * neutral fallback + the Day-24 empty state. (A `GET /seller/store` would make
 * this first-class — flagged for Orion.)
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

    const nudges = nudgesEnv.data ?? [];

    // Resolve the seller's OWN store + listings from a product they own. We pick
    // a seed product_id from their nudges (each nudge references one of their
    // listings), learn the store from its detail, then list the store's catalogue.
    let storeName = "Your store";
    let listings: SellerListing[] = [];
    const seedProductId = nudges[0]?.product_id;
    if (seedProductId) {
      try {
        const seedEnv = await apiFetch<BackendProductDetail>(
          `/products/${encodeURIComponent(seedProductId)}`,
          { token: auth.token, init: { cache: "no-store" } },
        );
        const store = seedEnv.data?.store;
        if (store) {
          storeName = store.name;
          const productsEnv = await apiFetch<BackendStoreProduct[]>(
            `/products?store_id=${encodeURIComponent(store.id)}&limit=100`,
            { token: auth.token, init: { cache: "no-store" } },
          );
          listings = toListings(productsEnv.data ?? []);
        }
      } catch {
        // Store resolution is best-effort — degrade to the neutral fallback +
        // empty listings table rather than failing the whole dashboard.
      }
    }

    const dashboard = toSellerDashboard(
      orders,
      orderDetails,
      nudges,
      storeName,
      listings,
    );
    const envelope: Envelope<SellerDashboard> = { data: dashboard, meta: null };
    return NextResponse.json(envelope);
  } catch (err) {
    return toErrorResponse(err, "Could not load the dashboard.");
  }
}
