import { NextResponse } from "next/server";
import type { Envelope, SearchMeta, SearchResult } from "@/lib/api-types";
import { EMPTY_QUERY, mockSearch, toSearchResult } from "@/lib/mock/catalog";

/**
 * MOCK `GET /search?q=` → `{ data: SearchResult[], meta: { ..., mode } }`.
 *
 * Drives the catalogue grid during local dev + the US-QA-D19 E2E while the live
 * backend (with real keyword/semantic retrieval) is on `integration/agents`,
 * not on this line. Same response envelope + `meta.mode` as the contract
 * (contract-v0.md §search), so flipping to live is a route-handler swap — the
 * `searchProducts()` client and the page consume the identical shape.
 *
 * Deterministic states for QA:
 *  - `q=zzzznoresults` (EMPTY_QUERY) → zero results → `search-empty-state`.
 *  - `q=boom`                        → 500 error envelope → error state.
 *  - anything else                   → matched rows (or all rows for browse).
 */
export function GET(request: Request): NextResponse {
  const q = new URL(request.url).searchParams.get("q")?.trim() ?? "";

  if (q.toLowerCase() === "boom") {
    return NextResponse.json(
      { error: { code: "internal_error", message: "Search is temporarily unavailable.", details: null } },
      { status: 500 },
    );
  }

  const results: SearchResult[] =
    q.toLowerCase() === EMPTY_QUERY ? [] : mockSearch(q).map(toSearchResult);

  const meta: SearchMeta = {
    next_cursor: null,
    limit: results.length,
    total: results.length,
    mode: "keyword",
  };

  const body: Envelope<SearchResult[]> = { data: results, meta };
  return NextResponse.json(body);
}
