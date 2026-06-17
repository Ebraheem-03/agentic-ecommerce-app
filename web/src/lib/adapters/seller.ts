/**
 * Seller contract → view-model adapters (Day-24 flip-to-live, ADR-0040;
 * fulfil-table wiring, ADR-0045 follow-up).
 *
 * The live backend has NO `/seller/dashboard` aggregate and no listings/inventory
 * endpoint. The FE dashboard view-model (`SellerDashboard`) is an FE-only
 * convenience that the seller proxy composes server-side by fanning out to the
 * live endpoints:
 *   - `GET /seller/orders`           → the orders the seller must fulfil
 *                                       (`OrderSummary[]`, no line snapshots),
 *   - `GET /seller/orders/{id}`      → that order's seller-scoped LINES
 *                                       (`SellerOrderDetail`; `items` are ONLY
 *                                       the caller's own store's lines, no leak),
 *   - `GET /seller/nudges`           → the agent-generated merchandising nudges.
 *
 * Per-line fulfil table (RESOLVED — Orion shipped `GET /seller/orders/{id}` this
 * session): the proxy fans out per order to collect each order's seller-scoped
 * lines, then flattens them into `SellerFulfilItem[]`. Each `items[*].id` is the
 * `order_item_id` that `PATCH /seller/order-items/{id}/fulfil` accepts, so the
 * fulfil action targets the real line. When a seller genuinely has no orders the
 * list is empty and the Day-24 empty state renders.
 *
 * Wire-casing note: despite the `CamelModel` name, the backend base model has no
 * camel alias generator, so `SellerOrderDetail` / `OrderItemOut` serialize in
 * snake_case (`order_number`, `title_snapshot`, `fulfil_status`, …) — same as the
 * buyer-side `OrderDetail`. The FE view-models already match that shape, so the
 * line fields pass through; we only project `order_number` down onto each line.
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
  OrderItemOut,
  OrderSummary,
  SellerDashboard,
  SellerFulfilItem,
  SellerListing,
} from "@/lib/api-types";

/**
 * `GET /seller/orders/{id}` wire shape — the order with ONLY this seller's lines.
 * Snake_case on the wire (see wire-casing note above). `items[*].id` is the
 * `order_item_id` the fulfil PATCH accepts.
 */
export interface SellerOrderDetail {
  id: string;
  order_number: string;
  status: string;
  currency: string;
  item_count: number;
  placed_at: string;
  items: OrderItemOut[];
}

/**
 * Flatten the per-order seller-scoped details into the fulfil table's row model.
 * Projects each order's `order_number` down onto its lines so a row can show
 * which order it belongs to. `id` stays the `order_item_id` (the fulfil target).
 */
export function toFulfilItems(
  orderDetails: SellerOrderDetail[],
): SellerFulfilItem[] {
  return orderDetails.flatMap((order) =>
    order.items.map((line) => ({
      id: line.id,
      order_number: order.order_number,
      title_snapshot: line.title_snapshot,
      options_snapshot: line.options_snapshot as Record<string, unknown>,
      qty: line.qty,
      unit_price_minor: line.unit_price_minor,
      currency: order.currency,
      fulfil_status: line.fulfil_status,
    })),
  );
}

/**
 * Compose the dashboard view-model from the live fan-out results. The orders the
 * seller must fulfil are surfaced as `OrderSummary` rows, and their seller-scoped
 * lines (fetched per order, concurrently) are flattened into `order_items`.
 * `listings` has no live source today (empty).
 */
export function toSellerDashboard(
  orders: OrderSummary[],
  orderDetails: SellerOrderDetail[],
  nudges: NudgeOut[],
): SellerDashboard {
  return {
    store_name: "Your store",
    listings: [] as SellerListing[],
    orders,
    order_items: toFulfilItems(orderDetails),
    nudges,
  };
}
