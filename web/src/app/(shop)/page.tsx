import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ProductThumb } from "@/components/shop/ProductThumb";
import { StockBadge } from "@/components/shop/StockBadge";
import { getFeaturedProducts } from "@/lib/product-data";
import { formatPrice } from "@/lib/shop-client";
import type { SearchResult } from "@/lib/api-types";

/**
 * Home — the editorial-gallery surface (ADR-0036, redesign per web/DESIGN.md).
 * Image-led: photography carries the page (real Unsplash, category-matched, all
 * verified 200). Composition is magazine rhythm, NOT uniform grids — a full-bleed
 * hero, an asymmetric collections feature (one dominant + two supporting), and the
 * live "Picked for the season" rail recomposed as a lead card + supporting trio.
 *
 * The concierge lives on `/search` (the route IS the conversation); the hero CTA
 * (`home-hero-cta`) enters it. Preserved: test-ids (home-page, home-hero-cta,
 * home-featured-rail), tokens as the only colour source, and the live
 * `getFeaturedProducts` path with its static fallback.
 *
 * Motion: a staggered page-load reveal (`.reveal` + `--reveal-delay`) and a calm
 * image scale on hover (`.img-zoom`); both have a `prefers-reduced-motion`
 * alternative defined in globals.css.
 */

const UNSPLASH = (id: string, w = 1600): string =>
  `https://images.unsplash.com/photo-${id}?auto=format&fit=crop&w=${w}&q=80`;

// Hero — a potter shaping clay on the wheel. The maker's-studio shot the whole
// brand voice (warm · hand-made · unhurried) is built around. Verified 200.
const HERO_IMAGE = UNSPLASH("1493106641515-6b5631de4bb9", 2000);

// Curated collections, now image-led. Each photo is category-matched and was
// verified to return 200 at w=1600 before shipping (no guessed IDs / 404s).
const COLLECTIONS = [
  {
    name: "The Slow Table",
    makers: "12 makers",
    blurb:
      "Stoneware, linen, and hand-thrown serving pieces for long, unhurried dinners.",
    image: UNSPLASH("1610701596007-11502861dcfa"),
    alt: "Hand-thrown ceramic cups with speckled stoneware glaze, grouped on a pale shelf.",
  },
  {
    name: "Quiet Corners",
    makers: "9 makers",
    blurb: "Textiles and warm light for the parts of home that go unnoticed.",
    image: UNSPLASH("1493663284031-b7e3aefcae8e"),
    alt: "A soft grey sofa layered with woven cushions in a bright, calm living room.",
  },
  {
    name: "Fire & Glaze",
    makers: "15 makers",
    blurb: "Wood-fired ceramics with finishes no two of which repeat.",
    image: UNSPLASH("1565193566173-7a0ee3dbe261"),
    alt: "Three matte stoneware bottles holding dried poppy seed heads against a dark ground.",
  },
] as const;

// Static fallback for the live "Picked" rail (catalogue unreachable). Maker is
// kept for context but no longer shown as a tracked eyebrow.
const FEATURED = [
  { slug: "wood-fired-serving-bowl", maker: "Field & Kiln", title: "Wood-fired serving bowl", price: "$92", stock: "in_stock" as const, tone: "from-[#7f8f6a] to-[#566543]" },
  { slug: "stoneware-mug-set-of-2", maker: "Ardal Clayworks", title: "Stoneware mug, set of 2", price: "$72", stock: "in_stock" as const, tone: "from-[#c66a45] to-[#8f3f23]" },
  { slug: "washed-linen-table-runner", maker: "Møller Textiles", title: "Washed linen table runner", price: "$64", stock: "low_stock" as const, tone: "from-[#e6cbab] to-[#cBA077]" },
  { slug: "ember-glaze-salt-cellar", maker: "North Light Co.", title: "Ember-glaze salt cellar", price: "$46", stock: "in_stock" as const, tone: "from-[#e9a766] to-[#cc7a33]" },
];

/** Quieter card metadata: title leads, maker reads as a calm line, price + stock anchor the foot. No tracked eyebrow. */
function CardMeta({
  maker,
  title,
  price,
  stock,
  className,
}: {
  maker: string;
  title: string;
  price: string;
  stock: SearchResult["stock"];
  className?: string;
}): JSX.Element {
  return (
    <div className={className ?? "flex flex-col gap-1.5 px-5 pb-5 pt-4"}>
      <h3 className="font-display text-h4 font-semibold leading-snug text-text">
        {title}
      </h3>
      <p className="text-small text-text-muted">by {maker}</p>
      <div className="mt-1.5 flex items-center justify-between gap-3">
        <span className="font-display text-h4 font-semibold text-text">{price}</span>
        <StockBadge stock={stock} />
      </div>
    </div>
  );
}

export default async function HomePage(): Promise<JSX.Element> {
  // Real "Picked for the season" listings (live catalogue); fall back to the
  // static editorial fixtures if the catalogue can't be reached.
  const live = await getFeaturedProducts(4);

  // Normalise live + fallback to one shape so the rail composes identically.
  const picks =
    live.length > 0
      ? live.map((p, i) => ({
          key: p.id,
          slug: p.slug,
          maker: p.maker,
          title: p.title,
          price: formatPrice(p.price_cents, p.currency),
          stock: p.stock,
          image: p.image_url,
          alt: p.image_alt ?? `${p.title} by ${p.maker}`,
          tone: FEATURED[i % FEATURED.length]?.tone ?? null,
        }))
      : FEATURED.map((p) => ({
          key: p.slug,
          slug: p.slug,
          maker: p.maker,
          title: p.title,
          price: p.price,
          stock: p.stock,
          image: null as string | null,
          alt: `${p.title} by ${p.maker}`,
          tone: p.tone,
        }));

  const [lead, ...rest] = picks;

  return (
    <div data-testid="home-page" className="flex flex-col gap-20 pb-24 sm:gap-28">
      {/* Hero — full-bleed maker's-studio image, headline overlaid. */}
      <section
        className="reveal relative -mx-4 mt-2 overflow-hidden rounded-b-[2rem] sm:-mx-8 sm:mt-4 sm:rounded-[2rem]"
        style={{ "--reveal-delay": "0ms" } as React.CSSProperties}
      >
        <div className="relative min-h-[26rem] sm:min-h-[34rem] lg:min-h-[40rem]">
          <ProductThumb
            src={HERO_IMAGE}
            alt="A potter's hands shaping a small clay vessel on a spinning wheel."
            className="absolute inset-0 h-full w-full"
            testId="home-hero-image"
          />
          {/* Warm scrim — keeps headline + body above 4.5:1 over the photo. */}
          <div
            aria-hidden="true"
            className="absolute inset-0 bg-gradient-to-r from-[rgba(20,14,9,0.86)] via-[rgba(20,14,9,0.62)] to-[rgba(20,14,9,0.18)]"
          />
          <div className="relative flex min-h-[26rem] flex-col justify-end gap-7 p-7 sm:min-h-[34rem] sm:p-12 lg:min-h-[40rem] lg:p-16">
            <div className="flex max-w-[24ch] flex-col gap-5">
              <h1
                className="font-display font-semibold leading-[1.02] tracking-tight text-[#fbf3ea] text-balance"
                style={{ fontSize: "clamp(2.6rem, 6.5vw, 5rem)" }}
              >
                The hearth for well-made things.
              </h1>
              <p className="max-w-[44ch] text-body-lg leading-relaxed text-[#efe2d4]">
                Tell Ember what you&rsquo;re furnishing, gifting, or mending. Our
                concierge knows every maker in the catalogue and recommends with
                reasons you can read, never hype.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3.5">
              <Button asChild variant="primary" size="lg" data-testid="home-hero-cta">
                <Link href="/search">Start a conversation</Link>
              </Button>
              <Button
                asChild
                variant="ghost"
                size="lg"
                className="border border-[rgba(251,243,234,0.5)] bg-[rgba(251,243,234,0.08)] text-[#fbf3ea] backdrop-blur-sm hover:bg-[rgba(251,243,234,0.16)] hover:text-[#fbf3ea]"
              >
                <Link href="/search">Browse the catalogue</Link>
              </Button>
            </div>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-small text-[#e3d4c4]">
              <span className="inline-flex items-center gap-2">
                <span className="inline-block h-2 w-2 rounded-full bg-[#7fb894]" aria-hidden="true" />
                1,240 independent makers
              </span>
              <span>Ships in recycled, plastic-free packaging</span>
            </div>
          </div>
        </div>
      </section>

      {/* Curated collections — asymmetric editorial split: one dominant feature
          beside two stacked supporting cards. Real photography throughout. */}
      <section
        className="reveal"
        style={{ "--reveal-delay": "120ms" } as React.CSSProperties}
      >
        <div className="mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
          <h2
            className="max-w-[18ch] font-display font-semibold tracking-tight text-text text-balance"
            style={{ fontSize: "clamp(1.9rem, 3.2vw, 2.75rem)" }}
          >
            Collections worth slowing down for
          </h2>
          <Button asChild variant="ghost" size="sm">
            <Link href="/search?view=collections">See all collections</Link>
          </Button>
        </div>

        <div className="grid gap-5 lg:grid-cols-12">
          {/* Dominant feature */}
          <Link
            href="/search?view=collections"
            className="group relative block overflow-hidden rounded-3xl no-underline shadow-[0_1px_2px_rgba(27,22,17,.04),0_16px_40px_-20px_rgba(27,22,17,.30)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong focus-visible:ring-offset-2 focus-visible:ring-offset-bg lg:col-span-7"
          >
            <ProductThumb
              src={COLLECTIONS[0].image}
              alt={COLLECTIONS[0].alt}
              imgClassName="img-zoom"
              className="aspect-[4/5] sm:aspect-[16/11] lg:aspect-auto lg:h-full lg:min-h-[30rem]"
            />
            <div
              aria-hidden="true"
              className="absolute inset-0 bg-gradient-to-t from-[rgba(20,14,9,0.9)] via-[rgba(20,14,9,0.45)] via-35% to-transparent"
            />
            <div className="absolute inset-x-0 bottom-0 flex flex-col gap-2 p-7 sm:p-8">
              <span className="text-small font-medium text-[#e8a866]">
                {COLLECTIONS[0].makers}
              </span>
              <h3
                className="font-display font-semibold leading-tight text-[#fbf3ea] text-balance"
                style={{ fontSize: "clamp(1.6rem, 3vw, 2.4rem)" }}
              >
                {COLLECTIONS[0].name}
              </h3>
              <p className="max-w-[42ch] text-body text-[#e3d4c4]">
                {COLLECTIONS[0].blurb}
              </p>
            </div>
          </Link>

          {/* Two stacked supporting cards */}
          <div className="grid gap-5 lg:col-span-5">
            {COLLECTIONS.slice(1).map((c) => (
              <Link
                key={c.name}
                href="/search?view=collections"
                className="group relative block overflow-hidden rounded-3xl no-underline shadow-[0_1px_2px_rgba(27,22,17,.04),0_14px_34px_-18px_rgba(27,22,17,.26)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
              >
                <ProductThumb
                  src={c.image}
                  alt={c.alt}
                  imgClassName="img-zoom"
                  className="aspect-[16/10] lg:aspect-auto lg:h-full lg:min-h-[14.25rem]"
                />
                <div
                  aria-hidden="true"
                  className="absolute inset-0 bg-gradient-to-t from-[rgba(20,14,9,0.9)] via-[rgba(20,14,9,0.5)] via-45% to-transparent"
                />
                <div className="absolute inset-x-0 bottom-0 flex flex-col gap-1.5 p-6">
                  <span className="text-small font-medium text-[#e8a866]">{c.makers}</span>
                  <h3 className="font-display text-h3 font-semibold text-[#fbf3ea]">
                    {c.name}
                  </h3>
                  <p className="max-w-[38ch] text-small text-[#e3d4c4]">{c.blurb}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Picked for the season — recomposed: one large lead card + a supporting
          trio. Live `getFeaturedProducts` data with the static fallback. */}
      <section
        className="reveal"
        data-testid="home-featured-rail"
        style={{ "--reveal-delay": "240ms" } as React.CSSProperties}
      >
        <div className="mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
          <div className="flex max-w-[40ch] flex-col gap-2">
            <h2
              className="font-display font-semibold tracking-tight text-text text-balance"
              style={{ fontSize: "clamp(1.9rem, 3.2vw, 2.75rem)" }}
            >
              Picked for the season
            </h2>
            <p className="text-body text-text-muted">
              A short list Ember keeps returning to, chosen for how the pieces
              live together.
            </p>
          </div>
          <Button asChild variant="ghost" size="sm">
            <Link href="/search">View all</Link>
          </Button>
        </div>

        <div className="grid gap-5 lg:grid-cols-12">
          {/* Lead pick */}
          {lead ? (
            <Link
              href={`/product/${lead.slug}`}
              className="group flex flex-col overflow-hidden rounded-3xl border border-border bg-surface no-underline shadow-[0_1px_2px_rgba(27,22,17,.04)] transition-shadow hover:shadow-[0_1px_2px_rgba(27,22,17,.04),0_18px_44px_-20px_rgba(27,22,17,.28)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong focus-visible:ring-offset-2 focus-visible:ring-offset-bg lg:col-span-7"
            >
              <ProductThumb
                src={lead.image}
                tone={lead.tone}
                alt={lead.alt}
                imgClassName="img-zoom"
                overlay="★ Picked"
                className="aspect-[4/3] lg:aspect-[16/10]"
              />
              <CardMeta
                maker={lead.maker}
                title={lead.title}
                price={lead.price}
                stock={lead.stock}
                className="flex flex-col gap-2 p-7"
              />
            </Link>
          ) : null}

          {/* Supporting trio */}
          <div className="grid gap-5 sm:grid-cols-3 lg:col-span-5 lg:grid-cols-1">
            {rest.map((p) => (
              <Link
                key={p.key}
                href={`/product/${p.slug}`}
                className="group flex flex-col overflow-hidden rounded-2xl border border-border bg-surface no-underline shadow-[0_1px_2px_rgba(27,22,17,.04)] transition-shadow hover:shadow-[0_1px_2px_rgba(27,22,17,.04),0_14px_34px_-18px_rgba(27,22,17,.24)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong focus-visible:ring-offset-2 focus-visible:ring-offset-bg sm:flex-col lg:flex-row"
              >
                <ProductThumb
                  src={p.image}
                  tone={p.tone}
                  alt={p.alt}
                  imgClassName="img-zoom"
                  className="aspect-[4/3] sm:aspect-square lg:aspect-square lg:w-[38%] lg:shrink-0"
                />
                <CardMeta
                  maker={p.maker}
                  title={p.title}
                  price={p.price}
                  stock={p.stock}
                  className="flex flex-1 flex-col justify-center gap-1.5 px-4 pb-4 pt-3 lg:py-4"
                />
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Value strip — kept, de-eyebrowed (heading-led). */}
      <section
        className="reveal"
        style={{ "--reveal-delay": "360ms" } as React.CSSProperties}
      >
        <div className="grid gap-x-10 gap-y-8 rounded-3xl border border-border bg-surface-muted p-8 sm:p-10 md:grid-cols-3">
          {[
            { h: "Recommends with reasons", p: "Every suggestion cites why it fits, by material, maker, and size, so you can disagree." },
            { h: "Tells you when it can’t", p: "If something’s out of stock or off-policy, Ember says so plainly and points to the source." },
            { h: "Makers paid fairly", p: "A flat, transparent fee. The price you pay is mostly the maker’s." },
          ].map((v) => (
            <div key={v.h} className="flex flex-col gap-2">
              <h3 className="font-display text-h3 font-semibold text-text">{v.h}</h3>
              <p className="text-small leading-relaxed text-text-muted">{v.p}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
