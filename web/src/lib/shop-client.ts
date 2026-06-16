import type {
  CartItemAdd,
  CartItemUpdate,
  CartOut,
  CheckoutRequest,
  Envelope,
  ErrorBody,
  FulfilRequest,
  NudgeOut,
  OrderDetail,
  OrderSummary,
  PaymentConfirmRequest,
  PaymentIntentOut,
  PaymentOut,
  ReturnCreate,
  ReturnOut,
  SellerDashboard,
  SellerFulfilItem,
} from "@/lib/api-types";

/**
 * Browser-side shop data client. Like the auth flow, the browser never calls the
 * FastAPI backend directly — it calls our same-origin Next route handlers under
 * `/api/*`, which (today) serve a MOCK fixture and (at the W3 gate) proxy the live
 * backend with the httpOnly session token attached server-side. The call sites
 * here don't change when we flip to live; only the route handlers do.
 */

const SHOP_API_BASE =
  process.env.NEXT_PUBLIC_SHOP_API_BASE?.replace(/\/$/, "") ?? "/api";

/** Format minor-unit money for display. Prices never travel pre-formatted. */
export function formatPrice(cents: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: cents % 100 === 0 ? 0 : 2,
  }).format(cents / 100);
}

function isErrorEnvelope(value: unknown): value is { error: ErrorBody } {
  return (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof (value as { error: unknown }).error === "object"
  );
}

/** Carries the canonical error body so call sites can branch on `code`. */
export class ShopError extends Error {
  readonly status: number;
  readonly body: ErrorBody;
  constructor(status: number, body: ErrorBody) {
    super(body.message);
    this.name = "ShopError";
    this.status = status;
    this.body = body;
  }
}

/** Shared JSON fetch → unwrap the `{data}` envelope or throw a typed ShopError. */
async function call<T>(
  path: string,
  init?: RequestInit & { fallbackMessage?: string },
): Promise<T> {
  const { fallbackMessage, ...rest } = init ?? {};
  const res = await fetch(`${SHOP_API_BASE}${path}`, {
    ...rest,
    headers: {
      Accept: "application/json",
      ...(rest.body ? { "Content-Type": "application/json" } : {}),
      ...rest.headers,
    },
  });
  const json = (await res.json().catch(() => null)) as unknown;

  if (!res.ok || isErrorEnvelope(json)) {
    const fallback: ErrorBody = {
      code: "internal_error",
      message: fallbackMessage ?? "Something went wrong. Please try again.",
      details: null,
    };
    throw new ShopError(res.status, isErrorEnvelope(json) ? json.error : fallback);
  }
  return (json as Envelope<T>).data;
}

/* ----------------------------- cart ----------------------------- */

export function getCart(): Promise<CartOut> {
  return call<CartOut>("/cart", { fallbackMessage: "Could not load your cart." });
}

export function addToCart(body: CartItemAdd): Promise<CartOut> {
  return call<CartOut>("/cart/items", {
    method: "POST",
    body: JSON.stringify(body),
    fallbackMessage: "Could not add to cart.",
  });
}

export function updateCartLine(
  lineId: string,
  body: CartItemUpdate,
): Promise<CartOut> {
  return call<CartOut>(`/cart/items/${lineId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
    fallbackMessage: "Could not update the cart.",
  });
}

export function removeCartLine(lineId: string): Promise<CartOut> {
  return call<CartOut>(`/cart/items/${lineId}`, {
    method: "DELETE",
    fallbackMessage: "Could not remove that item.",
  });
}

/* ---------------------------- orders ---------------------------- */

/** `POST /orders` — checkout (idempotent via the `Idempotency-Key` header). */
export function checkout(
  body: CheckoutRequest,
  idempotencyKey: string,
): Promise<OrderDetail> {
  return call<OrderDetail>("/orders", {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(body),
    fallbackMessage: "Could not place the order.",
  });
}

export function listOrders(): Promise<OrderSummary[]> {
  return call<OrderSummary[]>("/orders", { fallbackMessage: "Could not load your orders." });
}

export function getOrder(id: string): Promise<OrderDetail> {
  return call<OrderDetail>(`/orders/${id}`, { fallbackMessage: "Could not load that order." });
}

export function createPaymentIntent(orderId: string): Promise<PaymentIntentOut> {
  return call<PaymentIntentOut>(`/orders/${orderId}/payment-intent`, {
    method: "POST",
    fallbackMessage: "Could not start the payment.",
  });
}

export function confirmPayment(
  orderId: string,
  body: PaymentConfirmRequest,
): Promise<PaymentOut> {
  return call<PaymentOut>(`/orders/${orderId}/payment-confirm`, {
    method: "POST",
    body: JSON.stringify(body),
    fallbackMessage: "Could not confirm the payment.",
  });
}

/* ---------------------------- returns --------------------------- */

export function createReturn(
  orderId: string,
  body: ReturnCreate,
): Promise<ReturnOut> {
  return call<ReturnOut>(`/orders/${orderId}/returns`, {
    method: "POST",
    body: JSON.stringify(body),
    fallbackMessage: "Could not start the return.",
  });
}

export function listReturns(orderId: string): Promise<ReturnOut[]> {
  return call<ReturnOut[]>(`/orders/${orderId}/returns`, {
    fallbackMessage: "Could not load returns.",
  });
}

/* ---------------------------- seller ---------------------------- */

export function getSellerDashboard(): Promise<SellerDashboard> {
  return call<SellerDashboard>("/seller/dashboard", {
    fallbackMessage: "Could not load the dashboard.",
  });
}

export function acceptNudge(nudgeId: string): Promise<NudgeOut> {
  return call<NudgeOut>(`/seller/nudges/${nudgeId}/accept`, {
    method: "POST",
    body: JSON.stringify({}),
    fallbackMessage: "Could not accept the nudge.",
  });
}

export function fulfilOrderItem(
  itemId: string,
  body: FulfilRequest,
): Promise<SellerFulfilItem> {
  return call<SellerFulfilItem>(`/seller/order-items/${itemId}/fulfil`, {
    method: "PATCH",
    body: JSON.stringify(body),
    fallbackMessage: "Could not update fulfilment.",
  });
}
