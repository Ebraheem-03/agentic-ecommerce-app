import Link from "next/link";
import type { AgentRecommendation } from "@/lib/api-types";
import { formatPrice } from "@/lib/shop-client";
import { ProductThumb } from "@/components/shop/ProductThumb";
import { StockBadge } from "@/components/shop/StockBadge";

/**
 * In-chat generative product card — the grounded `done.recommendations[]` the
 * concierge surfaces. Deep-links into product detail (`/product/[slug]`). Wires
 * `agent-recommendation-card` + the defensible `agent-recommendation-reason`.
 * Tone for the placeholder swatch is derived from the title so a card reads
 * consistently with its grid/product-page counterpart.
 */
const TONES = [
  "from-[#7f8f6a] to-[#566543]",
  "from-[#c66a45] to-[#8f3f23]",
  "from-[#e6cbab] to-[#cBA077]",
  "from-[#e9a766] to-[#cc7a33]",
];

function toneFor(seed: string): string {
  let h = 0;
  for (const ch of seed) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return TONES[h % TONES.length] as string;
}

export function RecommendationCard({
  rec,
  onNavigate,
}: {
  rec: AgentRecommendation;
  onNavigate?: () => void;
}): JSX.Element {
  return (
    <Link
      href={`/product/${rec.slug}`}
      onClick={onNavigate}
      data-testid="agent-recommendation-card"
      className="group flex gap-3 rounded-[14px] border border-border bg-surface p-3 no-underline transition-colors hover:border-accent-strong/60 hover:bg-accent-tint/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong"
    >
      <ProductThumb
        tone={toneFor(rec.title)}
        alt={rec.image_alt}
        className="h-[64px] w-[64px] flex-none rounded-[10px]"
      />
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="truncate text-small font-semibold text-text">{rec.title}</span>
          <span className="flex-none font-display text-small font-semibold text-text">
            {formatPrice(rec.price_cents, rec.currency)}
          </span>
        </div>
        <span className="text-caption text-text-muted">{rec.maker}</span>
        <p data-testid="agent-recommendation-reason" className="text-caption leading-relaxed text-text-muted">
          <span className="font-semibold text-accent-text">Why: </span>
          {rec.reason}
        </p>
        <StockBadge stock={rec.stock} className="mt-0.5 self-start" />
      </div>
    </Link>
  );
}
