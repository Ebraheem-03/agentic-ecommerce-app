import type {
  FulfilStatus,
  NudgeOut,
  SellerDashboard,
  SellerFulfilItem,
  SellerListing,
  StockState,
} from "@/lib/api-types";
import { MOCK_PRODUCTS } from "@/lib/mock/catalog";

/**
 * MOCK seller dashboard store (ADR-0037). Backs the maker view: an
 * inventory/listings snapshot, orders awaiting fulfilment (`GET /seller/orders`
 * + `PATCH /seller/order-items/{id}/fulfil`), and the agent-generated
 * merchandising NUDGES (`GET /seller/nudges` + `.../accept`). The nudges are
 * Echo's merch-agent output, mocked here with grounded rationales. At the W3
 * gate the route handlers proxy `/seller/*` and this module is dropped.
 *
 * Scoped to one maker ("Ardal Clayworks") so the dashboard is coherent.
 */

const STORE_NAME = "Ardal Clayworks";

/** Deterministic per-variant inventory (mirrors the stock signal). */
const QTY: Record<StockState, number> = {
  in_stock: 24,
  low_stock: 4,
  out_of_stock: 0,
};

function listings(): SellerListing[] {
  // This maker's own listings, plus a couple of neighbours so the table reads.
  const ownSlugs = new Set([
    "stoneware-mug-set-of-2",
    "hand-pinched-olive-dish",
    "wood-fired-serving-bowl",
    "ember-glaze-salt-cellar",
  ]);
  return MOCK_PRODUCTS.filter((p) => ownSlugs.has(p.slug)).map((p) => ({
    product_id: p.id,
    slug: p.slug,
    title: p.title,
    status: "active" as const,
    price_minor: p.price_cents,
    currency: p.currency,
    qty_on_hand: QTY[p.stock],
    stock: p.stock,
  }));
}

/** Order lines awaiting this maker's fulfilment. Mutable fulfil status. */
const fulfilItems: SellerFulfilItem[] = [
  {
    id: "sfi_1",
    order_number: "HRTH-1051",
    title_snapshot: "Stoneware mug, set of 2",
    options_snapshot: { Glaze: "Ember" },
    qty: 1,
    unit_price_minor: 7200,
    currency: "USD",
    fulfil_status: "pending",
  },
  {
    id: "sfi_2",
    order_number: "HRTH-1051",
    title_snapshot: "Hand-pinched olive dish",
    options_snapshot: { Glaze: "Terracotta" },
    qty: 2,
    unit_price_minor: 3400,
    currency: "USD",
    fulfil_status: "pending",
  },
  {
    id: "sfi_3",
    order_number: "HRTH-1047",
    title_snapshot: "Wood-fired serving bowl",
    options_snapshot: { Glaze: "Deep moss" },
    qty: 1,
    unit_price_minor: 9200,
    currency: "USD",
    fulfil_status: "fulfilled",
  },
];

/** Agent-generated merchandising nudges, grounded in real catalog data. */
const nudges: NudgeOut[] = [
  {
    id: "nudge_mug_restock",
    product_id: "prod_mug_pair",
    headline: "Restock the ember mug set — it sells out fastest",
    reason:
      "The ember mug set has the highest sell-through of your listings (41 reviews, 4.7★) and only 4 left this week. Ember saw 6 buyers ask for it by name in the last 30 days.",
    suggested_change: { action: "restock", target_qty: 24 },
    slug: "stoneware-mug-set-of-2",
    product_title: "Stoneware mug, set of 2",
    accepted: false,
  },
  {
    id: "nudge_olive_bundle",
    product_id: "prod_olive",
    headline: "Bundle the olive dish with the serving bowl",
    reason:
      "62% of buyers who bought the wood-fired bowl also viewed the olive dish. A small-table bundle at $118 (vs $126 separately) lifts attach-rate without discounting either piece below your floor.",
    suggested_change: { action: "create_bundle", price_minor: 11800 },
    slug: "hand-pinched-olive-dish",
    product_title: "Hand-pinched olive dish",
    accepted: false,
  },
  {
    id: "nudge_salt_photo",
    product_id: "prod_salt",
    headline: "Add a lifestyle photo to the salt cellar",
    reason:
      "The salt cellar has one studio image; listings in your category with a by-the-stove lifestyle shot convert ~18% better. Strong 4.8★ rating means the traffic is there — the page just under-sells.",
    suggested_change: { action: "add_image", slot: "lifestyle" },
    slug: "ember-glaze-salt-cellar",
    product_title: "Ember-glaze salt cellar",
    accepted: false,
  },
];

export function getDashboard(): SellerDashboard {
  return {
    store_name: STORE_NAME,
    listings: listings(),
    orders: [],
    order_items: fulfilItems.map((f) => ({ ...f })),
    nudges: nudges.map((n) => ({ ...n })),
  };
}

/** Accept a nudge (audited, reversible). Returns the updated nudge. */
export function acceptNudge(id: string): NudgeOut | undefined {
  const nudge = nudges.find((n) => n.id === id);
  if (!nudge) return undefined;
  nudge.accepted = true;
  return { ...nudge };
}

/** Update a fulfilment line's status. Returns the updated line. */
export function fulfilItem(
  id: string,
  status: FulfilStatus,
): SellerFulfilItem | undefined {
  const item = fulfilItems.find((f) => f.id === id);
  if (!item) return undefined;
  item.fulfil_status = status;
  return { ...item };
}
