import Link from "next/link";
import { Button } from "@/components/ui/button";

/**
 * Home — token-truthful port of docs/brand/preview/screens/home.html. The agent
 * concierge panel is a static, on-brand preview here; the live streaming
 * generative-UI surface lands in a later story (it's the SSE contract surface).
 * Test-ids wired: home-page, home-hero-cta, home-featured-rail, agent-* panel.
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
  { maker: "Ardal Clayworks", title: "Ember stoneware mug", price: "$38", stock: "in", tone: "from-[#c66a45] to-[#8f3f23]" },
  { maker: "Møller Textiles", title: "Washed linen table runner", price: "$64", stock: "low", tone: "from-[#e6cbab] to-[#cBA077]" },
  { maker: "Field & Kiln", title: "Wood-fired serving bowl", price: "$92", stock: "in", tone: "from-[#7f8f6a] to-[#566543]" },
  { maker: "North Light Co.", title: "Hand-poured beeswax candle", price: "$28", stock: "in", tone: "from-[#b7ada1] to-[#8c8174]" },
];

export default function HomePage(): JSX.Element {
  return (
    <div data-testid="home-page">
      {/* Hero */}
      <section className="py-16">
        <div className="mx-auto max-w-[1200px] px-4 sm:px-8">
          <div className="grid items-center gap-14 lg:grid-cols-[1.05fr_.95fr]">
            <div className="flex flex-col gap-7">
              <span className="inline-flex items-center gap-2 text-caption font-medium uppercase tracking-wide text-accent-text before:inline-block before:h-px before:w-5 before:bg-accent-strong">
                Handmade, shoppable by conversation
              </span>
              <h1 className="font-display text-display font-semibold leading-[1.05] tracking-tight text-text">
                The hearth for
                <br />
                well-made things.
              </h1>
              <p className="max-w-[46ch] text-body-lg text-text-muted">
                Tell Hearth what you&rsquo;re furnishing, gifting, or mending. Our
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
                  <span className="inline-block h-2 w-2 rounded-full bg-success" />
                  1,240 independent makers
                </span>
                <span>Ships in recycled, plastic-free packaging</span>
              </div>
            </div>

            {/* Concierge preview */}
            <div
              data-testid="agent-chat-panel"
              aria-label="Hearth concierge"
              className="flex h-[440px] flex-col overflow-hidden rounded-[18px] border border-border bg-surface shadow-[0_1px_2px_rgba(27,22,17,.04),0_18px_44px_-22px_rgba(176,82,46,.28)]"
            >
              <div className="flex items-center gap-3 border-b border-border bg-gradient-to-b from-accent-tint to-surface px-[18px] py-4">
                <span className="grid h-[34px] w-[34px] flex-none place-items-center rounded-[10px] bg-accent" aria-hidden="true">
                  <span className="font-display text-small font-semibold text-n-900">H</span>
                </span>
                <div>
                  <div className="font-display text-small font-semibold text-text">
                    Hearth Concierge
                  </div>
                  <div className="inline-flex items-center gap-1.5 text-caption text-text-muted">
                    <span className="inline-block h-[7px] w-[7px] rounded-full bg-success" />
                    Online · grounded in the live catalogue
                  </div>
                </div>
              </div>
              <div
                data-testid="agent-message-list"
                role="log"
                aria-label="Conversation with the Hearth assistant"
                tabIndex={0}
                className="flex flex-1 flex-col gap-3.5 overflow-y-auto p-[18px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-inset"
              >
                <div data-testid="agent-message-assistant" className="max-w-[88%] self-start rounded-[14px_14px_14px_4px] bg-accent-tint px-3.5 py-3 text-small leading-relaxed text-text">
                  <span className="font-medium">Welcome in. What are you putting together?</span>
                  <br />I can help with a dinner set, a housewarming gift, or finding the maker behind something you already love.
                </div>
                <div data-testid="agent-message-user" className="max-w-[88%] self-end rounded-[14px_14px_4px_14px] bg-brand-tint px-3.5 py-2.5 text-small leading-relaxed text-text">
                  A wedding gift for friends who love to cook — around $90.
                </div>
                <div data-testid="agent-thinking-indicator" aria-live="polite" className="inline-flex items-center gap-2 text-caption font-medium text-accent-text">
                  <span>Looking through 1,240 makers</span>
                </div>
              </div>
              <form
                className="flex items-end gap-2.5 border-t border-border bg-surface p-3"
                action="/search"
              >
                <textarea
                  data-testid="agent-chat-input"
                  rows={1}
                  placeholder="Describe what you’re looking for…"
                  aria-label="Message Hearth concierge"
                  className="min-h-[44px] flex-1 resize-none rounded-xl border border-border bg-surface-muted px-3.5 py-2.5 text-small text-text placeholder:text-n-400 focus-visible:border-accent-strong focus-visible:outline-none"
                />
                <button
                  type="submit"
                  data-testid="agent-chat-send"
                  aria-label="Send"
                  className="grid h-11 w-11 flex-none place-items-center rounded-xl bg-accent text-n-900 transition-colors hover:bg-accent-strong"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              </form>
            </div>
          </div>
        </div>
      </section>

      {/* Curated collections */}
      <section className="py-10">
        <div className="mx-auto max-w-[1200px] px-4 sm:px-8">
          <div className="mb-7 flex items-end justify-between gap-4">
            <div className="flex flex-col gap-2">
              <span className="inline-flex items-center gap-2 text-caption font-medium uppercase tracking-wide text-accent-text before:inline-block before:h-px before:w-5 before:bg-accent-strong">
                Curated this week
              </span>
              <h2 className="font-display text-h2 font-semibold tracking-tight text-text">
                Collections worth slowing down for
              </h2>
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link href="/search?view=collections">See all collections →</Link>
            </Button>
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            {COLLECTIONS.map((c) => (
              <Link
                key={c.name}
                href="/search?view=collections"
                className="overflow-hidden rounded-2xl border border-border bg-surface no-underline shadow-[0_1px_2px_rgba(27,22,17,.04),0_8px_24px_-12px_rgba(27,22,17,.12)] transition-transform hover:-translate-y-0.5"
              >
                <div className={`grid aspect-[4/3] place-items-center bg-gradient-to-br ${c.tone} font-display text-sm text-white/90`}>
                  {c.name}
                </div>
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
        </div>
      </section>

      {/* Featured rail */}
      <section className="py-10" data-testid="home-featured-rail">
        <div className="mx-auto max-w-[1200px] px-4 sm:px-8">
          <div className="mb-6 flex items-center justify-between gap-4">
            <h2 className="font-display text-h3 font-semibold text-text">Picked for the season</h2>
            <Button asChild variant="ghost" size="sm">
              <Link href="/search">View all →</Link>
            </Button>
          </div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURED.map((p) => (
              <Link
                key={p.title}
                href="/search"
                className="overflow-hidden rounded-2xl border border-border bg-surface no-underline transition-all hover:-translate-y-0.5 hover:shadow-[0_1px_2px_rgba(27,22,17,.04),0_14px_34px_-16px_rgba(27,22,17,.22)]"
              >
                <div className={`grid aspect-[4/3] place-items-center bg-gradient-to-br ${p.tone} font-display text-sm text-white/90`}>
                  {p.title}
                </div>
                <div className="flex flex-col gap-2 px-[18px] pb-[18px] pt-4">
                  <span className="text-caption font-medium uppercase tracking-wide text-accent-text">
                    {p.maker}
                  </span>
                  <div className="text-h4 font-medium text-text">{p.title}</div>
                  <div className="flex items-center justify-between">
                    <span className="font-display font-semibold text-text">{p.price}</span>
                    {p.stock === "in" ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-success-tint px-2.5 py-1 text-caption font-medium text-[#2c5b41]">
                        <span className="inline-block h-[7px] w-[7px] rounded-full bg-success" />
                        In stock
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-warning-tint px-2.5 py-1 text-caption font-medium text-[#7a560f]">
                        <span className="inline-block h-[7px] w-[7px] rounded-full bg-warning" />
                        Low stock
                      </span>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Value strip */}
      <section className="py-16">
        <div className="mx-auto max-w-[1200px] px-4 sm:px-8">
          <div className="grid gap-10 rounded-2xl border border-border bg-surface-muted p-6 md:grid-cols-3">
            {[
              { h: "Recommends with reasons", p: "Every suggestion cites why it fits — material, maker, size — so you can disagree." },
              { h: "Tells you when it can’t", p: "If something’s out of stock or off-policy, Hearth says so plainly and points to the source." },
              { h: "Makers paid fairly", p: "A flat, transparent fee. The price you pay is mostly the maker’s." },
            ].map((v) => (
              <div key={v.h} className="flex flex-col gap-2">
                <h3 className="font-display text-h3 font-semibold text-text">{v.h}</h3>
                <p className="text-small text-text-muted">{v.p}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
