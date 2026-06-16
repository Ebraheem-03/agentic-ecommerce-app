import type {
  AddressIn,
  OrderDetail,
  OrderItemOut,
  OrderSummary,
  PaymentConfirmRequest,
  PaymentIntentOut,
  PaymentOut,
} from "@/lib/api-types";
import { MOCK_PRODUCTS } from "@/lib/mock/catalog";
import { getCart, resetCart } from "@/lib/mock/cart";

/**
 * MOCK orders + test-mode payment store (ADR-0037). Backs the agentic-checkout
 * two-step payment (`POST /orders` → `payment-intent` → `payment-confirm`), the
 * "my orders" list + detail timeline, and the returns flow — all deterministic
 * with the backend NOT live. At the W3 gate the route handlers proxy `/orders`
 * and this module is dropped.
 *
 * The deterministic decline is the CONTRACT switch, not an env flag:
 * `PaymentConfirmRequest.outcome="failed"` → 402 `payment_declined`, the payment
 * row lands `failed`, and the order STAYS `placed` (unpaid) so the UI can offer a
 * retry. `outcome="captured"` (default) → success.
 *
 * Idempotency: `POST /orders` replays return the same order for a given
 * Idempotency-Key, never a duplicate (contract §1.3).
 */

let orderSeq = 1000;
const orders = new Map<string, OrderDetail>();
const idempotency = new Map<string, string>(); // key -> order id

function money(items: OrderItemOut[]): number {
  return items.reduce((n, it) => n + it.unit_price_minor * it.qty, 0);
}

function slugForVariant(variantId: string | null): string | undefined {
  if (!variantId) return undefined;
  return MOCK_PRODUCTS.find((p) => p.variants.some((v) => v.id === variantId))?.slug;
}

/** Seed a couple of historical orders so "my orders" + returns render cold. */
function seedHistory(): void {
  if (orders.size > 0) return;

  // A DELIVERED order — return-eligible, exercises the returns UI.
  const deliveredItems: OrderItemOut[] = [
    {
      id: "oi_seed_runner",
      variant_id: "var_runner_oat",
      title_snapshot: "Washed linen table runner",
      options_snapshot: { Colour: "Oat" },
      store_name_snapshot: "Møller Textiles",
      unit_price_minor: 6400,
      qty: 1,
      fulfil_status: "fulfilled",
      slug: "washed-linen-table-runner",
    },
    {
      id: "oi_seed_olive",
      variant_id: "var_olive_clay",
      title_snapshot: "Hand-pinched olive dish",
      options_snapshot: { Glaze: "Terracotta" },
      store_name_snapshot: "Ardal Clayworks",
      unit_price_minor: 3400,
      qty: 2,
      fulfil_status: "fulfilled",
      slug: "hand-pinched-olive-dish",
    },
  ];
  const deliveredSubtotal = money(deliveredItems);
  const deliveredShip = 0;
  const deliveredTax = Math.round(deliveredSubtotal * 0.08);
  orders.set("ord_seed_delivered", {
    id: "ord_seed_delivered",
    order_number: "HRTH-1042",
    status: "delivered",
    total_minor: deliveredSubtotal + deliveredShip + deliveredTax,
    currency: "USD",
    item_count: deliveredItems.reduce((n, it) => n + it.qty, 0),
    placed_at: "2026-06-02T14:20:00.000Z",
    subtotal_minor: deliveredSubtotal,
    shipping_minor: deliveredShip,
    tax_minor: deliveredTax,
    ship_address: {
      name: "Maya Rowe",
      line1: "14 Kiln Lane",
      city: "Bristol",
      region: "",
      postal_code: "BS1 4DJ",
      country: "GB",
    },
    items: deliveredItems,
    payments: [
      {
        id: "pay_seed_delivered",
        status: "captured",
        provider_ref: "test_pi_seed_delivered",
        amount_minor: deliveredSubtotal + deliveredShip + deliveredTax,
        currency: "USD",
        created_at: "2026-06-02T14:21:00.000Z",
      },
    ],
    updated_at: "2026-06-05T11:00:00.000Z",
    return_eligible: true,
  });

  // A SHIPPED order — mid-timeline, no return yet.
  const shippedItems: OrderItemOut[] = [
    {
      id: "oi_seed_board",
      variant_id: "var_board_oak",
      title_snapshot: "Live-edge oak serving board",
      options_snapshot: { Wood: "Oak" },
      store_name_snapshot: "Bramble Wood",
      unit_price_minor: 8800,
      qty: 1,
      fulfil_status: "fulfilled",
      slug: "live-edge-oak-serving-board",
    },
  ];
  const shippedSubtotal = money(shippedItems);
  const shippedTax = Math.round(shippedSubtotal * 0.08);
  orders.set("ord_seed_shipped", {
    id: "ord_seed_shipped",
    order_number: "HRTH-1048",
    status: "shipped",
    total_minor: shippedSubtotal + shippedTax,
    currency: "USD",
    item_count: 1,
    placed_at: "2026-06-11T09:05:00.000Z",
    subtotal_minor: shippedSubtotal,
    shipping_minor: 0,
    tax_minor: shippedTax,
    ship_address: {
      name: "Maya Rowe",
      line1: "14 Kiln Lane",
      city: "Bristol",
      region: "",
      postal_code: "BS1 4DJ",
      country: "GB",
    },
    items: shippedItems,
    payments: [
      {
        id: "pay_seed_shipped",
        status: "captured",
        provider_ref: "test_pi_seed_shipped",
        amount_minor: shippedSubtotal + shippedTax,
        currency: "USD",
        created_at: "2026-06-11T09:06:00.000Z",
      },
    ],
    updated_at: "2026-06-12T16:30:00.000Z",
    return_eligible: false,
  });
}

seedHistory();

export interface CheckoutResult {
  order: OrderDetail;
  replayed: boolean;
}

/** Convert the open cart into a placed (unpaid) order. Idempotent on key. */
export function checkout(
  shipAddress: AddressIn,
  idempotencyKey?: string | null,
): CheckoutResult | { error: "empty_cart" } {
  if (idempotencyKey && idempotency.has(idempotencyKey)) {
    const existing = orders.get(idempotency.get(idempotencyKey) as string);
    if (existing) return { order: existing, replayed: true };
  }

  const cart = getCart();
  if (cart.items.length === 0) return { error: "empty_cart" };

  const items: OrderItemOut[] = cart.items.map((line) => ({
    id: `oi_${line.id}`,
    variant_id: line.variant_id,
    title_snapshot: line.title,
    options_snapshot: line.options,
    store_name_snapshot:
      MOCK_PRODUCTS.find((p) => p.id === line.product_id)?.maker ?? "Hearth maker",
    unit_price_minor: line.unit_price_minor,
    qty: line.qty,
    fulfil_status: "pending",
    slug: slugForVariant(line.variant_id),
  }));

  const subtotal = money(items);
  const tax = Math.round(subtotal * 0.08);
  const id = `ord_${++orderSeq}`;
  const now = new Date().toISOString();
  const order: OrderDetail = {
    id,
    order_number: `HRTH-${orderSeq + 100}`,
    status: "placed",
    total_minor: subtotal + tax,
    currency: cart.currency,
    item_count: items.reduce((n, it) => n + it.qty, 0),
    placed_at: now,
    subtotal_minor: subtotal,
    shipping_minor: 0,
    tax_minor: tax,
    ship_address: { ...shipAddress },
    items,
    payments: [],
    updated_at: now,
    return_eligible: false,
  };
  orders.set(id, order);
  if (idempotencyKey) idempotency.set(idempotencyKey, id);

  // Checkout consumes the open cart.
  resetCart(true);
  return { order, replayed: false };
}

export function getOrder(id: string): OrderDetail | undefined {
  return orders.get(id);
}

export function listOrders(): OrderSummary[] {
  return [...orders.values()]
    .sort((a, b) => b.placed_at.localeCompare(a.placed_at))
    .map((o) => ({
      id: o.id,
      order_number: o.order_number,
      status: o.status,
      total_minor: o.total_minor,
      currency: o.currency,
      item_count: o.item_count,
      placed_at: o.placed_at,
    }));
}

/** Create a test-mode intent for an order (idempotent per order). */
export function createIntent(orderId: string): PaymentIntentOut | undefined {
  const order = orders.get(orderId);
  if (!order) return undefined;
  const pending = order.payments.find((p) => p.status === "pending");
  const paymentId = pending?.id ?? `pay_${orderId}`;
  if (!pending) {
    const payment: PaymentOut = {
      id: paymentId,
      status: "pending",
      provider_ref: null,
      amount_minor: order.total_minor,
      currency: order.currency,
      created_at: new Date().toISOString(),
    };
    order.payments.push(payment);
  }
  return {
    payment_id: paymentId,
    client_secret: `test_secret_${orderId}`,
    status: "pending",
    amount_minor: order.total_minor,
    currency: order.currency,
  };
}

export interface ConfirmResult {
  payment: PaymentOut;
  declined: boolean;
}

/** Confirm the intent. `outcome="failed"` → decline (order stays placed). */
export function confirmPayment(
  orderId: string,
  body: PaymentConfirmRequest,
): ConfirmResult | undefined {
  const order = orders.get(orderId);
  if (!order) return undefined;
  const payment =
    order.payments.find((p) => p.id === body.payment_id) ??
    order.payments[order.payments.length - 1];
  if (!payment) return undefined;

  if (body.outcome === "failed") {
    payment.status = "failed";
    payment.provider_ref = `test_pi_failed_${orderId}`;
    order.updated_at = new Date().toISOString();
    return { payment, declined: true };
  }

  payment.status = "captured";
  payment.provider_ref = `test_pi_${orderId}`;
  order.status = "packed";
  order.updated_at = new Date().toISOString();
  return { payment, declined: false };
}

/** Mark an order delivered (used by returns seeding / lookups). */
export function markReturnRequested(orderId: string): void {
  const order = orders.get(orderId);
  if (order) order.updated_at = new Date().toISOString();
}
