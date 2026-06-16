import { notFound } from "next/navigation";
import Link from "next/link";
import type { Metadata } from "next";
import { getProduct } from "@/lib/product-data";
import { ProductThumb } from "@/components/shop/ProductThumb";
import { ProductBuyBox } from "@/components/shop/ProductBuyBox";

/**
 * `/product/[idOrSlug]` — product detail, token-truthful port of product.html.
 * The deep-link target for search-result and concierge recommendation cards.
 * The "ask about this" affordance from the hi-fi is now the layout-level docked
 * concierge (ADR-0036), so this page is the gallery + buy box; the buy box is a
 * client island (`ProductBuyBox`) for variants / qty / add-to-cart.
 *
 * Wires product-page / product-title / product-image / product-price (in the buy
 * box) / product-qty / product-add-to-cart / product-add-confirmation /
 * product-out-of-stock.
 */

interface PageProps {
  params: { idOrSlug: string };
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const product = await getProduct(params.idOrSlug);
  if (!product) return { title: "Not found · Hearth" };
  return {
    title: `${product.title} · ${product.maker} · Hearth`,
    description: product.description,
  };
}

function Stars({ rating }: { rating: number }): JSX.Element {
  const rounded = Math.round(rating);
  return (
    <span className="text-accent-text" aria-label={`Rated ${rating} of 5`}>
      {"★★★★★".slice(0, rounded)}
      <span className="text-n-300">{"★★★★★".slice(rounded)}</span>
    </span>
  );
}

const TRUST = [
  "Plastic-free packaging",
  "30-day returns",
  "Maker keeps 88%",
  "Breakage replaced free",
];

export default async function ProductPage({
  params,
}: PageProps): Promise<JSX.Element> {
  const product = await getProduct(params.idOrSlug);
  if (!product) notFound();

  const [hero, ...thumbs] = product.images;

  return (
    <div data-testid="product-page" className="py-10">
      <nav aria-label="Breadcrumb" className="mb-7 text-small text-text-muted">
        <Link href="/search" className="hover:text-text">Browse</Link>
        <span className="px-1.5" aria-hidden="true">/</span>
        <span className="text-text">{product.title}</span>
      </nav>

      <div className="grid items-start gap-10 lg:grid-cols-[1.05fr_1fr]">
        {/* Gallery */}
        <div className="flex flex-col gap-3">
          <ProductThumb
            testId="product-image"
            tone={hero?.tone}
            alt={hero?.alt ?? `${product.title} by ${product.maker}`}
            className="aspect-square rounded-[18px] border border-border"
          />
          {thumbs.length > 0 ? (
            <ul className="grid grid-cols-4 gap-3">
              {thumbs.map((img) => (
                <li key={img.id}>
                  <ProductThumb
                    tone={img.tone}
                    alt={img.alt}
                    className="aspect-square rounded-[12px] border border-border"
                  />
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        {/* Buy box */}
        <div className="flex flex-col gap-6 lg:sticky lg:top-[88px]">
          <div className="flex flex-col gap-2">
            <span className="text-caption font-medium uppercase tracking-wide text-accent-text">
              {product.maker}
              {product.maker_location ? ` · ${product.maker_location}` : ""}
            </span>
            <h1
              data-testid="product-title"
              className="font-display text-h1 font-semibold leading-tight tracking-tight text-text text-balance"
            >
              {product.title}
            </h1>
            {product.rating != null ? (
              <div className="flex items-center gap-2.5">
                <Stars rating={product.rating} />
                <span className="text-small text-text-muted">
                  {product.rating.toFixed(1)} · {product.review_count} reviews
                </span>
              </div>
            ) : null}
          </div>

          <ProductBuyBox product={product} />

          <hr className="border-border" />

          <ul className="grid grid-cols-2 gap-3">
            {TRUST.map((t) => (
              <li key={t} className="flex items-center gap-2.5 text-small text-text-muted">
                <span className="inline-block h-1.5 w-1.5 flex-none rounded-full bg-brand" aria-hidden="true" />
                {t}
              </li>
            ))}
          </ul>

          <p className="text-small text-text-muted">
            Questions about size, care, or the maker? Ask Ember in the concierge,
            answers come grounded in this maker&rsquo;s listing.
          </p>
        </div>
      </div>
    </div>
  );
}
