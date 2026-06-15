"use client";

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import type { SearchResult } from "@/lib/api-types";
import { formatPrice, searchProducts } from "@/lib/shop-client";
import { ProductThumb } from "@/components/shop/ProductThumb";
import { StockBadge } from "@/components/shop/StockBadge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { SearchIcon } from "@/components/shell/icons";

/**
 * Catalogue search — query box, results grid, and the empty / loading / error
 * states. Reads `?q=` from the URL so a deep-link (e.g. from the home hero) and
 * a typed query share one source of truth; submitting pushes `?q=` and refetches.
 * Wires search-page / search-input / search-submit / search-results /
 * search-result-card (+ inner title/price) / search-empty-state.
 */

type Status = "idle" | "loading" | "ready" | "error";

export function SearchView(): JSX.Element {
  const router = useRouter();
  const params = useSearchParams();
  const q = params.get("q") ?? "";

  const [draft, setDraft] = useState(q);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Keep the input in sync when the URL query changes (back/forward, deep-link).
  useEffect(() => {
    setDraft(q);
  }, [q]);

  const run = useCallback((query: string, signal: AbortSignal) => {
    if (query.trim().length === 0) {
      setStatus("idle");
      setResults([]);
      return;
    }
    setStatus("loading");
    setErrorMsg(null);
    searchProducts(query, signal)
      .then((res) => {
        if (signal.aborted) return;
        setResults(res.results);
        setStatus("ready");
      })
      .catch((err: unknown) => {
        if (signal.aborted || (err instanceof DOMException && err.name === "AbortError")) return;
        setErrorMsg(err instanceof Error ? err.message : "Search failed.");
        setStatus("error");
      });
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    run(q, ctrl.signal);
    return () => ctrl.abort();
  }, [q, run]);

  const onSubmit = (e: FormEvent): void => {
    e.preventDefault();
    const next = draft.trim();
    router.push(next ? `/search?q=${encodeURIComponent(next)}` : "/search");
  };

  const pickedCount = results.filter((r) => r.picked).length;

  return (
    <div data-testid="search-page" className="py-10">
      <form onSubmit={onSubmit} role="search" className="mb-7 flex items-center gap-2.5">
        <div className="relative flex-1">
          <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-text-muted">
            <SearchIcon />
          </span>
          <Input
            data-testid="search-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Ask Hearth, or search makers and goods…"
            aria-label="Search Hearth"
            className="pl-10"
          />
        </div>
        <Button type="submit" variant="brand" data-testid="search-submit">
          Search
        </Button>
      </form>

      {q.trim().length > 0 ? (
        <div className="mb-6 flex flex-col gap-1">
          <h1 className="font-display text-h2 font-semibold tracking-tight text-text text-balance">
            Results for &ldquo;{q}&rdquo;
          </h1>
          {status === "ready" ? (
            <p className="text-small text-text-muted" aria-live="polite">
              {results.length} {results.length === 1 ? "good" : "goods"}
              {pickedCount > 0 ? ` · ${pickedCount} of them Ember’s picks` : ""}
            </p>
          ) : null}
        </div>
      ) : (
        <div className="mb-6 flex flex-col gap-1">
          <h1 className="font-display text-h2 font-semibold tracking-tight text-text text-balance">
            Browse the catalogue
          </h1>
          <p className="text-small text-text-muted">
            Search above, or ask Ember in the concierge for a recommendation with reasons.
          </p>
        </div>
      )}

      {status === "loading" ? <ResultsSkeleton /> : null}

      {status === "error" ? (
        <div
          role="alert"
          className="rounded-2xl border border-error/40 bg-error-tint/50 p-6 text-small text-[#8a2f24]"
        >
          <p className="font-medium">{errorMsg ?? "Something went wrong."}</p>
          <p className="mt-1 text-text-muted">
            Try again, or ask Ember in the concierge to widen the search.
          </p>
        </div>
      ) : null}

      {status === "ready" && results.length === 0 ? (
        <div
          data-testid="search-empty-state"
          className="rounded-2xl border border-border bg-surface-muted p-8 text-center"
        >
          <h2 className="font-display text-h3 font-semibold text-text">No exact matches</h2>
          <p className="mx-auto mt-2 max-w-[52ch] text-small text-text-muted">
            Nothing in the catalogue matched that yet. The concierge can widen the
            budget or suggest a near-fit, just ask in the chat.
          </p>
        </div>
      ) : null}

      {(status === "ready" || status === "idle") && results.length > 0 ? (
        <div
          data-testid="search-results"
          className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3"
        >
          {results.map((r) => (
            <ResultCard key={r.id} result={r} />
          ))}
        </div>
      ) : null}

      {status === "idle" && results.length === 0 && q.trim().length === 0 ? (
        <BrowsePrompt />
      ) : null}
    </div>
  );
}

function ResultCard({ result }: { result: SearchResult }): JSX.Element {
  return (
    <Link
      href={`/product/${result.slug}`}
      data-testid="search-result-card"
      className="group overflow-hidden rounded-2xl border border-border bg-surface no-underline transition-all hover:-translate-y-0.5 hover:shadow-[0_1px_2px_rgba(27,22,17,.04),0_14px_34px_-16px_rgba(27,22,17,.22)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong"
    >
      <ProductThumb
        alt={result.image_alt}
        className="aspect-[4/3]"
        overlay={result.picked ? "★ Ember’s pick" : undefined}
      />
      <div className="flex flex-col gap-2 px-[18px] pb-[18px] pt-4">
        <span className="text-caption font-medium uppercase tracking-wide text-accent-text">
          {result.maker}
        </span>
        <div data-testid="search-result-title" className="text-h4 font-medium text-text">
          {result.title}
        </div>
        <div className="flex items-center justify-between">
          <span data-testid="search-result-price" className="font-display font-semibold text-text">
            {formatPrice(result.price_cents, result.currency)}
          </span>
          <StockBadge stock={result.stock} />
        </div>
      </div>
    </Link>
  );
}

function ResultsSkeleton(): JSX.Element {
  return (
    <div
      className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3"
      aria-hidden="true"
    >
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="overflow-hidden rounded-2xl border border-border bg-surface">
          <div className="aspect-[4/3] animate-pulse bg-surface-muted motion-reduce:animate-none" />
          <div className="flex flex-col gap-2 px-[18px] pb-[18px] pt-4">
            <div className="h-3 w-24 animate-pulse rounded bg-surface-muted motion-reduce:animate-none" />
            <div className="h-4 w-40 animate-pulse rounded bg-surface-muted motion-reduce:animate-none" />
            <div className="h-3 w-16 animate-pulse rounded bg-surface-muted motion-reduce:animate-none" />
          </div>
        </div>
      ))}
    </div>
  );
}

function BrowsePrompt(): JSX.Element {
  const SEEDS = ["wedding gift", "ceramics", "linen", "serving bowl"];
  return (
    <div className="rounded-2xl border border-dashed border-border bg-surface-muted/60 p-8 text-center">
      <p className="text-small text-text-muted">Try one of these to get started:</p>
      <div className="mt-3 flex flex-wrap justify-center gap-2">
        {SEEDS.map((s) => (
          <Link
            key={s}
            href={`/search?q=${encodeURIComponent(s)}`}
            className="rounded-full border border-border bg-surface px-3.5 py-1.5 text-caption text-text-muted no-underline transition-colors hover:border-accent-strong/60 hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong"
          >
            {s}
          </Link>
        ))}
      </div>
    </div>
  );
}
