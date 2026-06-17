import type {
  CartItemAdd,
  CartItemUpdate,
  CartOut,
  Envelope,
  ErrorBody,
  LoginRequest,
  OrderDetail,
  OrderSummary,
  PaymentConfirmRequest,
  PaymentIntentOut,
  PaymentOut,
  RegisterRequest,
  SessionOut,
  UserOut,
} from "@/lib/api-types";
import type {
  BackendProductDetail,
  BackendSearchRow,
} from "@/lib/adapters/catalog";
import type { BackendAddressIn } from "@/lib/adapters/order";

/**
 * Hearth API client.
 *
 * Talks the contract envelope (docs/api/contract-v0.md §1.1/§1.2): every 2xx is
 * `{ data, meta }`; every 4xx/5xx is `{ error: { code, message, details } }`.
 * Auth is an opaque server-side session token sent as `Authorization: Bearer`.
 *
 * Token persistence (documented choice): the token is stored in an **httpOnly
 * cookie** set by our own Next.js route handlers (`/api/auth/*`), never in
 * localStorage. The browser never reads the token — it calls the same-origin
 * route handlers, which attach the Bearer header server-side. This keeps the
 * token out of JS (XSS-safe), survives reload, and makes the client free of any
 * browser-storage assumption (per the test guidance).
 */

// Backend origin for SERVER-SIDE calls only (route handlers / server components;
// the browser never calls the backend directly — it goes through same-origin
// `/api/*`). Resolved at RUNTIME from `API_BASE_URL` so it can be set per
// environment without a rebuild (in docker-compose this is `http://api:8000`,
// the api service host — `localhost` would resolve to the web container itself).
// `NEXT_PUBLIC_API_BASE_URL` stays supported as a fallback for local `next dev`,
// but note NEXT_PUBLIC_* is inlined at build time and can't be set per-container.
export const API_BASE_URL = (
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8000"
).replace(/\/$/, "");

/** Thrown on any non-2xx; carries the canonical error body for the UI. */
export class ApiError extends Error {
  readonly status: number;
  readonly body: ErrorBody;

  constructor(status: number, body: ErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function isErrorEnvelope(value: unknown): value is { error: ErrorBody } {
  return (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof (value as { error: unknown }).error === "object"
  );
}

interface RequestOptions {
  method?: string;
  /** Bearer token to attach server-side (route handlers pass it from cookie). */
  token?: string | null;
  body?: unknown;
  /**
   * Forwarded to fetch (e.g. `cache: "no-store"`). Extra `headers` here are
   * merged onto the computed ones (used to pass `Idempotency-Key` through).
   */
  init?: Omit<RequestInit, "method" | "body"> & {
    headers?: Record<string, string>;
  };
}

/**
 * Low-level call against the real backend. Returns the unwrapped `data`.
 * Used by server-side code (route handlers, server components) that holds the
 * token. The browser does NOT call this directly — it goes through `/api/*`.
 */
export async function apiFetch<T>(
  path: string,
  { method = "GET", token, body, init }: RequestOptions = {},
): Promise<Envelope<T>> {
  const { headers: extraHeaders, ...restInit } = init ?? {};
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (extraHeaders) Object.assign(headers, extraHeaders);

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    ...restInit,
  });

  let payload: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!res.ok) {
    if (isErrorEnvelope(payload)) {
      throw new ApiError(res.status, payload.error);
    }
    throw new ApiError(res.status, {
      code: "internal_error",
      message: `Request failed (${res.status}).`,
      details: null,
    });
  }

  return payload as Envelope<T>;
}

/** Typed auth operations against the backend (server-side). */
export const authApi = {
  register(body: RegisterRequest): Promise<Envelope<SessionOut>> {
    return apiFetch<SessionOut>("/auth/register", { method: "POST", body });
  },
  login(body: LoginRequest): Promise<Envelope<SessionOut>> {
    return apiFetch<SessionOut>("/auth/login", { method: "POST", body });
  },
  logout(token: string): Promise<Envelope<{ revoked: boolean }>> {
    return apiFetch<{ revoked: boolean }>("/auth/logout", {
      method: "POST",
      token,
    });
  },
  me(token: string): Promise<Envelope<UserOut>> {
    return apiFetch<UserOut>("/auth/me", { method: "GET", token });
  },
};

/**
 * Typed shop operations against the live backend (server-side only). These are
 * called by the `/api/*` route handlers, which hold the session token and map
 * the (nested) wire shapes → the FE view-models via `@/lib/adapters/*`. The
 * browser never calls these directly.
 *
 * Returns the RAW (nested) backend shapes — the route handler does the
 * adapter mapping so the mapping stays in one obvious place.
 */
export const shopApi = {
  /* catalog */
  search(q: string, token: string): Promise<Envelope<BackendSearchRow[]>> {
    return apiFetch<BackendSearchRow[]>(`/search?q=${encodeURIComponent(q)}`, {
      token,
      init: { cache: "no-store" },
    });
  },
  product(
    idOrSlug: string,
    token: string,
  ): Promise<Envelope<BackendProductDetail>> {
    return apiFetch<BackendProductDetail>(
      `/products/${encodeURIComponent(idOrSlug)}`,
      { token, init: { cache: "no-store" } },
    );
  },

  /* cart */
  getCart(token: string): Promise<Envelope<CartOut>> {
    return apiFetch<CartOut>("/cart", { token, init: { cache: "no-store" } });
  },
  addCartItem(body: CartItemAdd, token: string): Promise<Envelope<CartOut>> {
    return apiFetch<CartOut>("/cart/items", { method: "POST", body, token });
  },
  updateCartItem(
    id: string,
    body: CartItemUpdate,
    token: string,
  ): Promise<Envelope<CartOut>> {
    return apiFetch<CartOut>(`/cart/items/${id}`, {
      method: "PATCH",
      body,
      token,
    });
  },
  removeCartItem(id: string, token: string): Promise<Envelope<CartOut>> {
    return apiFetch<CartOut>(`/cart/items/${id}`, { method: "DELETE", token });
  },

  /* orders + payments */
  checkout(
    body: { ship_address: BackendAddressIn; idempotency_key?: string | null },
    token: string,
    idempotencyKey: string | null,
  ): Promise<Envelope<OrderDetail>> {
    return apiFetch<OrderDetail>("/orders", {
      method: "POST",
      body,
      token,
      init: idempotencyKey
        ? { headers: { "Idempotency-Key": idempotencyKey } }
        : undefined,
    });
  },
  listOrders(token: string): Promise<Envelope<OrderSummary[]>> {
    return apiFetch<OrderSummary[]>("/orders", {
      token,
      init: { cache: "no-store" },
    });
  },
  getOrder(id: string, token: string): Promise<Envelope<OrderDetail>> {
    return apiFetch<OrderDetail>(`/orders/${id}`, {
      token,
      init: { cache: "no-store" },
    });
  },
  paymentIntent(
    orderId: string,
    token: string,
    idempotencyKey: string | null,
  ): Promise<Envelope<PaymentIntentOut>> {
    return apiFetch<PaymentIntentOut>(`/orders/${orderId}/payment-intent`, {
      method: "POST",
      token,
      init: idempotencyKey
        ? { headers: { "Idempotency-Key": idempotencyKey } }
        : undefined,
    });
  },
  paymentConfirm(
    orderId: string,
    body: PaymentConfirmRequest,
    token: string,
  ): Promise<Envelope<PaymentOut>> {
    return apiFetch<PaymentOut>(`/orders/${orderId}/payment-confirm`, {
      method: "POST",
      body,
      token,
    });
  },
};
