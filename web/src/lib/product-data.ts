import { ApiError, shopApi } from "@/lib/api";
import { getSessionToken } from "@/lib/session";
import { toProductDetail, toSearchResult } from "@/lib/adapters/catalog";
import type { ProductDetail, SearchResult } from "@/lib/api-types";

/**
 * Server-side product resolver for the detail route (Day-22 flip-to-live,
 * ADR-0040). Calls the live `GET /products/{idOrSlug}` and maps the nested wire
 * shape → the FE `ProductDetail` view-model via `toProductDetail`. The PDP page
 * is unchanged in shape — it already consumes the flat `ProductDetail` (now
 * `await`s this resolver since it's a network call).
 *
 * The endpoint is public; we attach the session token if present (harmless, and
 * keeps the proxy posture consistent). A missing product → `null` so the page
 * renders `notFound()`; any other fault also resolves to `null` rather than
 * 500-ing the whole route.
 */
export async function getProduct(
  idOrSlug: string,
): Promise<ProductDetail | null> {
  const token = getSessionToken();
  try {
    const { data } = await shopApi.product(idOrSlug, token ?? "");
    return toProductDetail(data);
  } catch (err) {
    if (err instanceof ApiError) return null;
    return null;
  }
}

/**
 * Server-side featured-rail resolver for the home page. Pulls a handful of live
 * active products (`GET /products`) and flattens them to `SearchResult[]` so the
 * "Picked for the season" rail shows REAL listings + imagery instead of static
 * fixtures. Any fault degrades to an empty rail (the home page renders without
 * it) rather than 500-ing the route. Public endpoint; token attached if present.
 */
export async function getFeaturedProducts(
  limit = 4,
): Promise<SearchResult[]> {
  const token = getSessionToken();
  try {
    const { data } = await shopApi.products({ limit }, token ?? "");
    return (data ?? []).map(toSearchResult);
  } catch {
    return [];
  }
}
