import type { ProductDetail } from "@/lib/api-types";
import { findProduct } from "@/lib/mock/catalog";

/**
 * Server-side product resolver for the detail route. Today it reads the MOCK
 * catalogue fixture directly (the live `GET /products/{id}` backend is on
 * `integration/agents`, not on this line). At the W3 gate this becomes an
 * `apiFetch<ProductDetail>("/products/{id}")` call with the session token, and
 * the page is unchanged — it already consumes the `ProductDetail` contract shape.
 */
export function getProduct(idOrSlug: string): ProductDetail | null {
  const p = findProduct(idOrSlug);
  if (!p) return null;
  // Strip the mock-only fields (keywords/picked/tone) down to the contract shape.
  const { keywords: _k, picked: _p, tone: _t, ...detail } = p;
  void _k;
  void _p;
  void _t;
  return detail;
}
