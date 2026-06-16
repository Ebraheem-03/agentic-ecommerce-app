import { ApiError, shopApi } from "@/lib/api";
import { getSessionToken } from "@/lib/session";
import { toProductDetail } from "@/lib/adapters/catalog";
import type { ProductDetail } from "@/lib/api-types";

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
