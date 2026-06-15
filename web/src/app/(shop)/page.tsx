import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ProductThumb } from "@/components/shop/ProductThumb";
import { StockBadge } from "@/components/shop/StockBadge";

/**
 * Home — token-truthful port of docs/brand/preview/screens/home.html. The
 * conversational concierge is no longer embedded here: per ADR-0036 it is the
 * PERSISTENT docked panel provided by the `(shop)` layout (right gutter on
 * desktop, invokable sheet on mobile). The hero CTA opens it; this page is the
 * editorial landing. Test-ids: home-page, home-hero-cta, home-featured-rail.
 */

const COLLECTIONS = [
  {
    name: "The Slow Table",
    makers: "12 makers",
    blurb: "Stoneware, linen, and hand-thrown serving pieces for long dinners.",
    tone: "from-[#c9744f] to-[#a8431f]",
  },
  {
    name: "Quiet Corners",
    makers: "9 makers",
    blurb: "Textiles and warm light for the parts of home that go unnoticed.",
    tone: "from-[#9aa888] to-[#6f8060]",
  },
  {
    name: "Fire & Glaze",
    makers: "15 makers",
    blurb: "Wood-fired ceramics with finishes no two of which repeat.",
    tone: "from-[#e9a766] to-[#cc7a33]",
  },
];

const FEATURED = [
  { slug: "wood-fired-serving-bowl", maker: "Field & Kiln", title: "Wood-fired serving bowl", price: "$92", stock: "in_stock" as const, tone: "from-[#7f8f6a] to-[#566543]" },
  { slug: "stoneware-mug-set-of-2", maker: "Ardal Clayworks", title: "Stoneware mug, set of 2", price: "$72", stock: "in_stock" as const, tone: "from-[#c66a45] to-[#8f3f23]" },
  { slug: "washed-linen-table-runner", maker: "Møller Textiles", title: "Washed linen table runner", price: "$64", stock: "low_stock" as const, tone: "from-[#e6cbab] to-[#cBA077]" },
  { slug: "ember-glaze-salt-cellar", maker: "North Light Co.", title: "Ember-glaze salt cellar", price: "$46", stock: "in_stock" as const, tone: "from-[#e9a766] to-[#cc7a33]" },
];

export default function HomePage(): JSX.Element {
  return (
    <div data-testid="home-page" className="flex flex-col gap-2">
      {/* Hero */}
      <section className="py-14">
        <div className="flex max-w-[58ch] flex-col gap-7">
          <span className="inline-flex items-center gap-2 text-caption font-medium uppercase tracking-wide text-accent-text before:inline-block before:h-px before:w-5 before:bg-accent-strong">
            Handmade, shoppable by conversation
          </span>
          <h1 className="font-display text-display font-semibold leading-[1.05] tracking-tight text-text text-balance">
            The hearth for well-made things.
          </h1>
          <p className="max-w-[46ch] text-body-lg text-text-muted">
            Tell Ember what you&rsquo;re furnishing, gifting, or mending. Our
            concierge knows every maker in the catalogue and recommends with
            reasons &mdash; never hype.
          </p>
          <div className="flex flex-wrap items-center gap-4">
            <Button asChild variant="primary" size="lg" data-testid="home-hero-cta">
              <Link href="/search">Start a conversation</Link>
            </Button>
            <Button asChild variant="secondary" size="lg">
              <Link href="/search">Browse the catalogue</Link>
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-6 text-small text-text-muted">
            <span className="inline-flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full bg-success" aria-hidden="true" />
              1,240 independent makers
            </span>
            <span>Ships in recycled, plastic-free packaging</span>
          </div>
        </div>
      </section>

      {/* Curated collections */}
      <section className="py-10">
        <div className="mb-7 flex items-end justify-between gap-4">
          <div className="flex flex-col gap-2">
            <span className="inline-flex items-center gap-2 text-caption font-medium uppercase tracking-wide text-accent-text before:inline-block before:h-px before:w-5 before:bg-accent-strong">
              Curated this week
            </span>
            <h2 className="font-display text-h2 font-semibold tracking-tight text-text text-balance">
              Collections worth slowing down for
            </h2>
          </div>
          <Button asChild variant="ghost" size="sm">
            <Link href="/search?view=collections">See all collections</Link>
          </Button>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
          {COLLECTIONS.map((c) => (
            <Link
              key={c.name}
              href="/search?view=collections"
              className="overflow-hidden rounded-2xl border border-border bg-surface no-underline shadow-[0_1px_2px_rgba(27,22,17,.04),0_8px_24px_-12px_rgba(27,22,17,.12)] transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong"
            >
              <ProductThumb tone={c.tone} className="aspect-[4/3] font-display text-sm text-white/90" />
              <div className="flex flex-col gap-2 p-6">
                <span className="text-caption font-medium uppercase tracking-wide text-accent-text">
                  {c.makers}
                </span>
                <h3 className="font-display text-h3 font-semibold text-text">{c.name}</h3>
                <p className="text-small text-text-muted">{c.blurb}</p>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Featured rail */}
      <section className="py-10" data-testid="home-featured-rail">
        <div className="mb-6 flex items-center justify-between gap-4">
          <h2 className="font-display text-h3 font-semibold text-text">Picked for the season</h2>
          <Button asChild variant="ghost" size="sm">
            <Link href="/search">View all</Link>
          </Button>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
          {FEATURED.map((p) => (
            <Link
              key={p.slug}
              href={`/product/${p.slug}`}
              className="overflow-hidden rounded-2xl border border-border bg-surface no-underline transition-all hover:-translate-y-0.5 hover:shadow-[0_1px_2px_rgba(27,22,17,.04),0_14px_34px_-16px_rgba(27,22,17,.22)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong"
            >
              <ProductThumb tone={p.tone} className="aspect-[4/3]" />
              <div className="flex flex-col gap-2 px-[18px] pb-[18px] pt-4">
                <span className="text-caption font-medium uppercase tracking-wide text-accent-text">
                  {p.maker}
                </span>
                <div className="text-h4 font-medium text-text">{p.title}</div>
                <div className="flex items-center justify-between">
                  <span className="font-display font-semibold text-text">{p.price}</span>
                  <StockBadge stock={p.stock} />
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Value strip */}
      <section className="py-14">
        <div className="grid gap-10 rounded-2xl border border-border bg-surface-muted p-6 sm:grid-cols-2 xl:grid-cols-3">
          {[
            { h: "Recommends with reasons", p: "Every suggestion cites why it fits, by material, maker, and size, so you can disagree." },
            { h: "Tells you when it can’t", p: "If something’s out of stock or off-policy, Ember says so plainly and points to the source." },
            { h: "Makers paid fairly", p: "A flat, transparent fee. The price you pay is mostly the maker’s." },
          ].map((v) => (
            <div key={v.h} className="flex flex-col gap-2">
              <h3 className="font-display text-h3 font-semibold text-text">{v.h}</h3>
              <p className="text-small text-text-muted">{v.p}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
