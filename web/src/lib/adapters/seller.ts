/**
 * Seller contract → view-model adapters (Day-24 flip-to-live, ADR-0040).
 *
 * The live backend has NO `/seller/dashboard` aggregate, no listings/inventory
 * endpoint, and `GET /seller/orders` returns whole `OrderSummary` rows (no per-
 * line snapshots). The FE dashboard view-model (`SellerDashboard`) is an FE-only
 * convenience that the seller proxy composes server-side by fanning out to the
 * live endpoints:
 *   - `GET /seller/orders`  → the orders the seller must fulfil (`OrderSummary[]`),
 *   - `GET /seller/nudges`  → the agent-generated merchandising nudges.
 *
 * KNOWN BACKEND GAP (flagged for Atlas/Orion — Day 24):
 *   The dashboard's per-line fulfil table needs `SellerFulfilItem[]` (title /
 *   options / qty / price per line). There is NO live source for it: a seller
 *   cannot read a buyer's order detail (`GET /orders/{id}` is buyer-owner-scoped
 *   → 404 for the seller), and both `GET /seller/orders` and the fulfil response
 *   return only `OrderSummary` (no items). So `order_items` is left EMPTY and the
 *   `orders` summaries are surfaced instead. The fulfil flow (`PATCH
 *   /seller/order-items/{id}/fulfil`) also can't be exercised from the UI until
 *   the backend exposes seller-scoped order LINES. See the report.
 *
 * Other gaps resolved client-side:
 *   - `listings` (inventory snapshot): no live endpoint → empty array.
 *   - `store_name`: not on `OrderSummary`/`NudgeOut` → neutral fallback.
 *   - `NudgeOut.slug` / `product_title` / `accepted`: display-only FE fields the
 *     backend doesn't return → derived/omitted (the card degrades gracefully).
 *
 * Mapping lives here so the route handler stays thin and the components unchanged.
 */
import type {
  NudgeOut,
  OrderSummary,
  SellerDashboard,
  SellerFulfilItem,
  SellerListing,
} from "@/lib/api-types";

/**
 * Compose the dashboard view-model from the live fan-out results. `order_items`
 * and `listings` have no live source today (empty — see KNOWN BACKEND GAP above);
 * the orders the seller must fulfil are surfaced as `OrderSummary` rows.
 */
export function toSellerDashboard(
  orders: OrderSummary[],
  nudges: NudgeOut[],
): SellerDashboard {
  return {
    store_name: "Your store",
    listings: [] as SellerListing[],
    orders,
    order_items: [] as SellerFulfilItem[],
    nudges,
  };
}
