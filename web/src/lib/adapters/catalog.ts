/**
 * Contract → view-model adapters (Day-22 flip-to-live, ADR-0040).
 *
 * The live backend returns NESTED catalog shapes (`product.store.name`,
 * `product.from_price_minor`, `product.primary_image.alt`, …). The FE
 * view-models in `@/lib/api-types` are FLAT (`maker`, `price_cents`,
 * `image_alt`). These mappers live in ONE place so the route handlers and
 * server components stay thin and the components are unchanged.
 *
 * Money note: the FE field is still called `price_cents` (legacy name) but it
 * carries minor units — we set it straight from the backend `*_minor` value.
 */
import type {
  AgentRecommendation,
  ProductDetail,
  ProductImage,
  ProductVariant,
  SearchResult,
  StockState,
} from "@/lib/api-types";

/* ----------------------- backend (wire) shapes ----------------------- */

interface BackendStore {
  id: string;
  name: string;
  slug: string;
  location: string | null;
  status: string;
}

interface BackendImage {
  id: string;
  url: string;
  alt: string | null;
  position: number;
  variant_id: string | null;
}

interface BackendVariant {
  id: string;
  sku: string;
  options: Record<string, unknown>;
  price_minor: number;
  currency: string;
  is_active: boolean;
  in_stock: boolean;
  restock_eta_days: number | null;
}

/** `ProductSummary` on the wire — shared by search rows, recs, and detail. */
export interface BackendProductSummary {
  id: string;
  title: string;
  slug: string;
  category: string;
  status: string;
  store: BackendStore;
  from_price_minor: number;
  currency: string;
  stock: StockState;
  primary_image: BackendImage | null;
  rating_avg: number | null;
  rating_count: number;
}

/** `ProductDetail` on the wire — `ProductSummary` + the detail-only fields. */
export interface BackendProductDetail extends BackendProductSummary {
  description: string;
  attributes: Record<string, unknown>;
  variants: BackendVariant[];
  images: BackendImage[];
  created_at: string;
  updated_at: string;
}

/** A `GET /search` row: `{ product: ProductSummary, score }`. */
export interface BackendSearchRow {
  product: BackendProductSummary;
  score: number;
}

/** A live agent `done`-frame recommendation (nests `ProductSummary`). */
export interface BackendRecommendation {
  product: BackendProductSummary;
  reason: string;
}

/* ------------------------------ mappers ------------------------------ */

/** Flatten a wire `ProductSummary` → FE `SearchResult`. */
export function toSearchResult(p: BackendProductSummary): SearchResult {
  return {
    id: p.id,
    slug: p.slug,
    title: p.title,
    maker: p.store.name,
    price_cents: p.from_price_minor,
    currency: p.currency,
    stock: p.stock,
    image_alt: p.primary_image?.alt ?? null,
  };
}

/** `GET /search` → `SearchResult[]`. */
export function toSearchResults(rows: BackendSearchRow[]): SearchResult[] {
  return rows.map((row) => toSearchResult(row.product));
}

function toProductImage(img: BackendImage): ProductImage {
  return {
    id: img.id,
    alt: img.alt ?? "",
    // No `tone` from live — components fall back to a token placeholder when absent.
  };
}

function toProductVariant(v: BackendVariant): ProductVariant {
  // The wire carries an options dict; the FE renders a single name/value pair.
  const [optName, optValue] = Object.entries(v.options)[0] ?? ["", ""];
  return {
    id: v.id,
    option_name: String(optName),
    option_value: String(optValue ?? ""),
    stock: v.in_stock ? "in_stock" : "out_of_stock",
  };
}

/** `GET /products/{idOrSlug}` → FE `ProductDetail`. */
export function toProductDetail(p: BackendProductDetail): ProductDetail {
  return {
    id: p.id,
    slug: p.slug,
    title: p.title,
    maker: p.store.name,
    maker_location: p.store.location,
    price_cents: p.from_price_minor,
    currency: p.currency,
    stock: p.stock,
    description: p.description,
    rating: p.rating_avg,
    review_count: p.rating_count,
    images: p.images.map(toProductImage),
    variants: p.variants.map(toProductVariant),
  };
}

/** A live agent recommendation → FE `AgentRecommendation` (same flatten as search). */
export function toAgentRecommendation(
  r: BackendRecommendation,
): AgentRecommendation {
  const p = r.product;
  return {
    product_id: p.id,
    slug: p.slug,
    title: p.title,
    maker: p.store.name,
    price_cents: p.from_price_minor,
    currency: p.currency,
    stock: p.stock,
    reason: r.reason,
    image_alt: p.primary_image?.alt ?? null,
  };
}
