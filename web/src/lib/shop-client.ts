import type {
  CartItemAdd,
  CartOut,
  Envelope,
  ErrorBody,
  SearchMeta,
  SearchResult,
} from "@/lib/api-types";

/**
 * Browser-side shop data client. Like the auth flow, the browser never calls
 * the FastAPI backend directly — it calls our same-origin Next route handlers
 * under `/api/*`, which (today) serve a MOCK fixture and (at the W3 gate) proxy
 * the live backend with the httpOnly session token attached server-side. The
 * call sites here don't change when we flip to live; only the route handlers do.
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

export interface SearchResponse {
  results: SearchResult[];
  mode: SearchMeta["mode"];
}

/** `GET /search?q=` → results grid. Resolves to `{ results, mode }`. */
export async function searchProducts(
  q: string,
  signal?: AbortSignal,
): Promise<SearchResponse> {
  const res = await fetch(
    `${SHOP_API_BASE}/search?q=${encodeURIComponent(q)}`,
    { signal, headers: { Accept: "application/json" } },
  );
  const json = (await res.json()) as unknown;

  if (!res.ok || isErrorEnvelope(json)) {
    const body = isErrorEnvelope(json)
      ? json.error
      : ({ code: "internal_error", message: "Search failed.", details: null } as ErrorBody);
    throw new ShopError(res.status, body);
  }

  const env = json as Envelope<SearchResult[]>;
  const meta = env.meta as SearchMeta | null;
  return { results: env.data, mode: meta?.mode ?? "keyword" };
}

/** `POST /cart/items` → updated cart. Used by the optimistic add-to-cart. */
export async function addToCart(body: CartItemAdd): Promise<CartOut> {
  const res = await fetch(`${SHOP_API_BASE}/cart/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  const json = (await res.json()) as unknown;

  if (!res.ok || isErrorEnvelope(json)) {
    const fallback: ErrorBody = {
      code: "internal_error",
      message: "Could not add to cart.",
      details: null,
    };
    throw new ShopError(res.status, isErrorEnvelope(json) ? json.error : fallback);
  }
  return (json as Envelope<CartOut>).data;
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
