import { Suspense } from "react";
import { SearchView } from "@/components/shop/SearchView";

/**
 * `/search` — the traditional catalogue results grid (ADR-0036). Plain
 * browse/scan in the main column; the conversational concierge is the docked
 * panel from the `(shop)` layout. The grid is fed by `GET /search?q=` (served by
 * the mock route handler today; flips to the live backend at the W3 gate).
 *
 * `SearchView` is a client component that reads `?q=` and owns the
 * loading/empty/error/results states. Wrapped in Suspense because it uses
 * `useSearchParams`.
 */
export default function SearchPage(): JSX.Element {
  return (
    <Suspense fallback={<div data-testid="search-page" className="py-16" />}>
      <SearchView />
    </Suspense>
  );
}
