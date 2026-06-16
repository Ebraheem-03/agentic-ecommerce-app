import type { CartItemOut, CartOut } from "@/lib/api-types";
import { MOCK_PRODUCTS } from "@/lib/mock/catalog";

/**
 * MOCK cart store (ADR-0037). A process-local, in-memory cart so the cart +
 * agentic-checkout pages render deterministically with the backend NOT live.
 * The Next route handlers (`GET /cart`, `POST|PATCH|DELETE /cart/items`) read
 * and mutate this single module-scoped cart; at the W3 gate the handlers proxy
 * the real `/cart` service and this module is no longer referenced.
 *
 * Determinism for the [REVIEW] render + E2E:
 *  - the cart SEEDS with two in-stock lines (bowl + mug-set), so `/cart` and the
 *    `/checkout` approval gate have real content on a cold load — no setup steps.
 *  - `resetCart()` (driven by `GET /cart?reset=empty`) clears to the empty state.
 */

const CURRENCY = "USD";

/** Resolve a variant → its product + display fields from the shared fixture. */
function resolveVariant(variantId: string):
  | {
      product: (typeof MOCK_PRODUCTS)[number];
      variant: (typeof MOCK_PRODUCTS)[number]["variants"][number];
    }
  | undefined {
  for (const product of MOCK_PRODUCTS) {
    const variant = product.variants.find((v) => v.id === variantId);
    if (variant) return { product, variant };
  }
  return undefined;
}

function lineFrom(variantId: string, qty: number, addedAt: string): CartItemOut | null {
  const found = resolveVariant(variantId);
  if (!found) return null;
  const { product, variant } = found;
  return {
    id: `line_${variant.id}`,
    variant_id: variant.id,
    product_id: product.id,
    title: product.title,
    sku: variant.id.replace(/^var_/, "SKU-").toUpperCase(),
    options: { [variant.option_name]: variant.option_value },
    unit_price_minor: product.price_cents,
    currency: product.currency,
    qty,
    line_total_minor: product.price_cents * qty,
    in_stock: variant.stock !== "out_of_stock",
    added_at: addedAt,
    option_value: variant.option_value,
    slug: product.slug,
  };
}

/** The seed lines — two in-stock makers so the cart is non-empty by default. */
function seedLines(): CartItemOut[] {
  const t = "2026-06-16T09:00:00.000Z";
  return [
    lineFrom("var_bowl_moss", 1, t),
    lineFrom("var_mug_ember", 2, t),
  ].filter((l): l is CartItemOut => l !== null);
}

let lines: CartItemOut[] = seedLines();

function recompute(): CartOut {
  const subtotal = lines.reduce((n, l) => n + l.line_total_minor, 0);
  const itemCount = lines.reduce((n, l) => n + l.qty, 0);
  return {
    id: "cart_mock",
    status: "open",
    items: lines,
    subtotal_minor: subtotal,
    currency: CURRENCY,
    item_count: itemCount,
    updated_at: new Date().toISOString(),
  };
}

/** Lazily get the open cart. */
export function getCart(): CartOut {
  return recompute();
}

/** Clear to the empty state (drives the empty-cart UI deterministically). */
export function resetCart(empty: boolean): CartOut {
  lines = empty ? [] : seedLines();
  return recompute();
}

/** Add or increment a variant. Returns null when the variant is unknown. */
export function addLine(variantId: string, qty: number): CartOut | null {
  const found = resolveVariant(variantId);
  if (!found) return null;
  const existing = lines.find((l) => l.variant_id === variantId);
  if (existing) {
    existing.qty += qty;
    existing.line_total_minor = existing.unit_price_minor * existing.qty;
  } else {
    const line = lineFrom(variantId, qty, new Date().toISOString());
    if (line) lines.push(line);
  }
  return recompute();
}

/** Set a line's absolute quantity (>0). Returns null when the line is unknown. */
export function setLineQty(lineId: string, qty: number): CartOut | null {
  const line = lines.find((l) => l.id === lineId);
  if (!line) return null;
  line.qty = Math.max(1, Math.floor(qty));
  line.line_total_minor = line.unit_price_minor * line.qty;
  return recompute();
}

/** Remove a line. Returns null when the line is unknown. */
export function removeLine(lineId: string): CartOut | null {
  const before = lines.length;
  lines = lines.filter((l) => l.id !== lineId);
  if (lines.length === before) return null;
  return recompute();
}

/** True when the variant is out of stock (drives the 409 path). */
export function variantOutOfStock(variantId: string): boolean {
  return resolveVariant(variantId)?.variant.stock === "out_of_stock";
}
