import type {
  AgentRecommendation,
  ProductDetail,
  SearchResult,
} from "@/lib/api-types";

/**
 * MOCK catalogue fixture — the single source of truth the mock `/api/search`,
 * `/api/agent/*`, and `/api/product` handlers all read from, so deep-links from
 * a rec card or a search card resolve to a real product page during local dev
 * and the US-QA-D19 E2E. NOT shipped to the live backend; at the W3 gate the
 * route handlers proxy FastAPI and this module is no longer referenced.
 *
 * Tones map to the hi-fi `.ph-*` placeholder swatches (no real image pipeline
 * yet); `image_alt` is meaningful alt text for the a11y A8 contract.
 */

interface MockProduct extends ProductDetail {
  /** Lower-cased keywords the mock keyword search matches against. */
  keywords: string[];
  /** Whether the concierge surfaces this as a "Picked" result. */
  picked: boolean;
  tone: string;
}

export const MOCK_PRODUCTS: MockProduct[] = [
  {
    id: "prod_bowl",
    slug: "wood-fired-serving-bowl",
    title: "Wood-fired serving bowl",
    maker: "Field & Kiln",
    maker_location: "Bristol, UK",
    price_cents: 9200,
    currency: "USD",
    stock: "in_stock",
    description:
      "Thrown and wood-fired in small batches, so the glaze breaks differently on every piece. Generous enough for a salad to share; food-safe and dishwasher-fine.",
    rating: 4.8,
    review_count: 64,
    tone: "from-[#7f8f6a] to-[#566543]",
    picked: true,
    keywords: ["bowl", "serving", "ceramic", "kitchen", "cook", "gift", "table", "dinner"],
    images: [
      { id: "img_bowl_1", alt: "Wood-fired stoneware serving bowl, deep moss glaze, photographed from above", tone: "from-[#7f8f6a] to-[#566543]" },
      { id: "img_bowl_2", alt: "Side profile of the serving bowl showing the wood-fired rim", tone: "from-[#9aa888] to-[#6f8060]" },
      { id: "img_bowl_3", alt: "The bowl holding a green salad on a linen cloth", tone: "from-[#b7ada1] to-[#8c8174]" },
      { id: "img_bowl_4", alt: "Close-up of the glaze break across the bowl's surface", tone: "from-[#c9744f] to-[#a8431f]" },
    ],
    variants: [
      { id: "var_bowl_moss", option_name: "Glaze", option_value: "Deep moss", stock: "in_stock" },
      { id: "var_bowl_ash", option_name: "Glaze", option_value: "Ash grey", stock: "in_stock" },
      { id: "var_bowl_ember", option_name: "Glaze", option_value: "Ember", stock: "out_of_stock" },
    ],
  },
  {
    id: "prod_mug_pair",
    slug: "stoneware-mug-set-of-2",
    title: "Stoneware mug, set of 2",
    maker: "Ardal Clayworks",
    maker_location: "Cardigan, Wales",
    price_cents: 7200,
    currency: "USD",
    stock: "in_stock",
    description:
      "A pair of hand-thrown stoneware mugs in a warm ember glaze that matches the serving bowl's maker family. Comfortable handle, holds a generous pour.",
    rating: 4.7,
    review_count: 41,
    tone: "from-[#c66a45] to-[#8f3f23]",
    picked: true,
    keywords: ["mug", "mugs", "cup", "stoneware", "ceramic", "kitchen", "cook", "gift", "pair", "set"],
    images: [
      { id: "img_mug_1", alt: "A pair of ember-glaze stoneware mugs side by side", tone: "from-[#c66a45] to-[#8f3f23]" },
      { id: "img_mug_2", alt: "One mug held to show the curve of the handle", tone: "from-[#e9a766] to-[#cc7a33]" },
    ],
    variants: [
      { id: "var_mug_ember", option_name: "Glaze", option_value: "Ember", stock: "in_stock" },
      { id: "var_mug_moss", option_name: "Glaze", option_value: "Deep moss", stock: "in_stock" },
    ],
  },
  {
    id: "prod_runner",
    slug: "washed-linen-table-runner",
    title: "Washed linen table runner",
    maker: "Møller Textiles",
    maker_location: "Copenhagen, DK",
    price_cents: 6400,
    currency: "USD",
    stock: "low_stock",
    description:
      "Stonewashed pure linen with a soft, lived-in drape from the first use. Oeko-Tex certified; machine-washable and only gets better with age.",
    rating: 4.9,
    review_count: 28,
    tone: "from-[#e6cbab] to-[#cBA077]",
    picked: false,
    keywords: ["linen", "runner", "table", "textile", "cloth", "dinner", "gift"],
    images: [
      { id: "img_runner_1", alt: "Washed linen table runner draped down a wooden dining table", tone: "from-[#e6cbab] to-[#cBA077]" },
    ],
    variants: [
      { id: "var_runner_oat", option_name: "Colour", option_value: "Oat", stock: "low_stock" },
      { id: "var_runner_clay", option_name: "Colour", option_value: "Clay", stock: "low_stock" },
    ],
  },
  {
    id: "prod_olive",
    slug: "hand-pinched-olive-dish",
    title: "Hand-pinched olive dish",
    maker: "Ardal Clayworks",
    maker_location: "Cardigan, Wales",
    price_cents: 3400,
    currency: "USD",
    stock: "in_stock",
    description:
      "A small pinched dish for olives, salt, or the odds and ends of a shared meal. Each one finds its own shape in the hand.",
    rating: 4.6,
    review_count: 19,
    tone: "from-[#c9744f] to-[#a8431f]",
    picked: false,
    keywords: ["olive", "dish", "ceramic", "kitchen", "small", "table", "gift"],
    images: [
      { id: "img_olive_1", alt: "Hand-pinched ceramic olive dish holding green olives", tone: "from-[#c9744f] to-[#a8431f]" },
    ],
    variants: [
      { id: "var_olive_clay", option_name: "Glaze", option_value: "Terracotta", stock: "in_stock" },
    ],
  },
  {
    id: "prod_salt",
    slug: "ember-glaze-salt-cellar",
    title: "Ember-glaze salt cellar",
    maker: "North Light Co.",
    maker_location: "Portland, US",
    price_cents: 4600,
    currency: "USD",
    stock: "in_stock",
    description:
      "A lidded salt cellar in the ember glaze, sized to sit by the stove. Wide mouth for a pinching hand.",
    rating: 4.8,
    review_count: 22,
    tone: "from-[#e9a766] to-[#cc7a33]",
    picked: false,
    keywords: ["salt", "cellar", "ceramic", "kitchen", "cook", "ember", "gift"],
    images: [
      { id: "img_salt_1", alt: "Ember-glaze ceramic salt cellar with its lid resting beside it", tone: "from-[#e9a766] to-[#cc7a33]" },
    ],
    variants: [
      { id: "var_salt_ember", option_name: "Glaze", option_value: "Ember", stock: "in_stock" },
    ],
  },
  {
    id: "prod_board",
    slug: "live-edge-oak-serving-board",
    title: "Live-edge oak serving board",
    maker: "Bramble Wood",
    maker_location: "Cumbria, UK",
    price_cents: 8800,
    currency: "USD",
    stock: "in_stock",
    description:
      "A live-edge oak board finished with food-safe oil, for cheese, bread, or a slow grazing dinner. The grain is one of a kind.",
    rating: 4.9,
    review_count: 37,
    tone: "from-[#b7ada1] to-[#8c8174]",
    picked: false,
    keywords: ["oak", "board", "wood", "serving", "cheese", "kitchen", "cook", "gift", "table"],
    images: [
      { id: "img_board_1", alt: "Live-edge oak serving board with cheese and bread", tone: "from-[#b7ada1] to-[#8c8174]" },
    ],
    variants: [
      { id: "var_board_oak", option_name: "Wood", option_value: "Oak", stock: "in_stock" },
    ],
  },
];

/** Shape a product into a `SearchResult` row. */
export function toSearchResult(p: MockProduct): SearchResult {
  return {
    id: p.id,
    slug: p.slug,
    title: p.title,
    maker: p.maker,
    price_cents: p.price_cents,
    currency: p.currency,
    stock: p.stock,
    image_alt: p.images[0]?.alt ?? null,
    picked: p.picked,
  };
}

/** Shape a product into an in-chat `AgentRecommendation` with a "why". */
export function toRecommendation(
  p: MockProduct,
  reason: string,
): AgentRecommendation {
  return {
    product_id: p.id,
    slug: p.slug,
    title: p.title,
    maker: p.maker,
    price_cents: p.price_cents,
    currency: p.currency,
    stock: p.stock,
    reason,
    image_alt: p.images[0]?.alt ?? null,
  };
}

/** Naive keyword match for the mock search; the real backend owns retrieval. */
export function mockSearch(q: string): MockProduct[] {
  const terms = q.toLowerCase().split(/[^a-z0-9$]+/).filter(Boolean);
  if (terms.length === 0) return MOCK_PRODUCTS;
  const scored = MOCK_PRODUCTS.map((p) => {
    const hay = [p.title, p.maker, ...p.keywords].join(" ").toLowerCase();
    const score = terms.reduce((n, t) => n + (hay.includes(t) ? 1 : 0), 0);
    return { p, score };
  });
  const hits = scored.filter((s) => s.score > 0);
  // No keyword hits → return everything so the grid is still useful (browse).
  // The dedicated empty-state query is the sentinel below.
  return (hits.length > 0 ? hits : scored)
    .sort((a, b) => b.score - a.score || Number(b.p.picked) - Number(a.p.picked))
    .map((s) => s.p);
}

/** Resolve a product by id OR slug for the detail page / deep-links. */
export function findProduct(idOrSlug: string): MockProduct | undefined {
  return MOCK_PRODUCTS.find((p) => p.id === idOrSlug || p.slug === idOrSlug);
}

/** Sentinel query that forces the empty-state (so Juno can assert it). */
export const EMPTY_QUERY = "zzzznoresults";
