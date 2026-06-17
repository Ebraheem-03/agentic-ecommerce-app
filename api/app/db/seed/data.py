"""The Hearth seed content — believable artisan/maker marketplace (US-E3-03).

Pure data (no DB calls). Natural keys (email, slug, sku, order_number) drive the
idempotent upserts in ``run.py``. Voice follows the brand brief: warm, plain-spoken,
honest. Policy bodies are written as genuine, quotable prose — they are the RAG
source the support agent retrieves over (feeds US-QA-D05 golden answers), so return
windows / shipping times / etc. are concrete.
"""

from __future__ import annotations

from itertools import count
from typing import Any, TypedDict

# --------------------------------------------------------------------------- imagery
# Curated, category-matched product photography for the image-led "editorial gallery"
# design. Each entry is an Unsplash *direct asset* photo ID — the URL we build returns
# HTTP 200 directly (no 302 redirect like the old picsum seeds) and is high enough
# resolution for full-bleed editorial use. Every ID in these pools was verified to
# resolve 200 before commit (see the seed task's curl loop).
#
# Pools are keyed by *semantic subject* (not store), so a product is matched to the
# kind of thing it is — ceramics → mugs/bowls/stoneware, woodwork → trays/boards, etc.
# A product is assigned a photo deterministically by its slug (stable across reseeds),
# and the modulo over a 3–5 deep pool means products in the same category don't all
# share a single photo.
_CATEGORY_IMAGES: dict[str, list[str]] = {
    # mugs, bowls, plates, stoneware vases
    "ceramics": [
        "1514228742587-6b1558fcca3d",
        "1556910103-1c02745aae4d",
        "1610701596007-11502861dcfa",
        "1565193566173-7a0ee3dbe261",
        "1493106641515-6b5631de4bb9",
    ],
    # wallets, belts, totes/bags, small leather goods
    "leather": [
        "1627123424574-724758594e93",
        "1604644401890-0bd678c83788",
        "1548036328-c9fa89d128fa",
        "1591561954557-26941169b49e",
        "1553062407-98eeb64c6a62",
    ],
    # linens, napkins, throws, blankets, woven towels
    "textiles": [
        "1584100936595-c0654b55a2e2",
        "1522771739844-6a9f6d5f14af",
        "1616627561839-074385245ff6",
        "1576566588028-4147f3842f27",
        "1600369671236-e74521d4b6ad",
    ],
    # wooden boards, trays, carved utensils
    "woodwork": [
        "1593618998160-e34014e67546",
        "1578991624414-276ef23a534f",
        "1556909114-f6e7ad7d3136",
        "1610701596061-2ecf227e85b2",
        "1605883705077-8d3d3cebe78c",
    ],
    # poured candles in glass / vessels
    "candle": [
        "1603006905003-be475563bc59",
        "1572726729207-a78d6feb18d7",
        "1518972559570-7cc1309f3229",
    ],
    # tins, balms, soaps, apothecary
    "balm": [
        "1556228578-8c89e6adf883",
        "1556228720-195a672e8a03",
        "1570172619644-dfd03ed5d881",
        "1601049541289-9b1b7bbbfe19",
    ],
}


# Per-group round-robin cursor. Products are assigned a photo in declaration order, so
# the Nth product of a category gets pool[N % len(pool)] — this *guarantees* variety
# within a category (no two adjacent products collide until the pool wraps), unlike a
# per-slug hash which can pile several products onto one photo by chance. Declaration
# order is fixed in this module, so assignments are stable across reseeds (idempotent).
_group_cursors: dict[str, Any] = {}


def _img(slug: str, group: str) -> str:
    """Curated, category-matched, direct-200 product image URL.

    Assigns the next photo in ``group``'s Unsplash pool, round-robin in product
    declaration order, so photos are varied within a category yet deterministic and
    stable across reseeds. The asset URL returns 200 directly — no redirect — and is
    sized for the full-bleed editorial gallery (1200px, auto-format, cropped square).

    ``slug`` is accepted for call-site readability / future per-slug overrides.
    """
    pool = _CATEGORY_IMAGES[group]
    cursor = _group_cursors.setdefault(group, count())
    photo_id = pool[next(cursor) % len(pool)]
    return f"https://images.unsplash.com/photo-{photo_id}?w=1200&q=80&auto=format&fit=crop"


class UserSeed(TypedDict):
    email: str
    display_name: str
    role: str


class VariantSeed(TypedDict):
    sku: str
    options: dict[str, Any]
    price_minor: int
    qty_on_hand: int
    qty_reserved: int
    restock_eta_days: int | None


class ReviewSeed(TypedDict):
    author_email: str
    rating: int
    title: str
    body: str


class ProductSeed(TypedDict):
    slug: str
    title: str
    category: str
    description: str
    attributes: dict[str, Any]
    image_url: str
    image_alt: str
    variants: list[VariantSeed]
    reviews: list[ReviewSeed]


class StoreSeed(TypedDict):
    slug: str
    name: str
    owner_email: str
    location: str
    bio: str
    products: list[ProductSeed]


class PolicySeed(TypedDict):
    store_slug: str | None  # None = platform-level
    kind: str
    title: str
    body: str


# --------------------------------------------------------------------------- users
USERS: list[UserSeed] = [
    # buyers
    {"email": "ada@buyers.hearth.test", "display_name": "Ada Whitfield", "role": "buyer"},
    {"email": "ben@buyers.hearth.test", "display_name": "Ben Okafor", "role": "buyer"},
    {"email": "cora@buyers.hearth.test", "display_name": "Cora Lindqvist", "role": "buyer"},
    {"email": "deepa@buyers.hearth.test", "display_name": "Deepa Rao", "role": "buyer"},
    {"email": "evan@buyers.hearth.test", "display_name": "Evan Marsh", "role": "buyer"},
    # sellers (one per store)
    {"email": "mara@makers.hearth.test", "display_name": "Mara Sólveig", "role": "seller"},
    {"email": "tomas@makers.hearth.test", "display_name": "Tomás Herrera", "role": "seller"},
    {"email": "ines@makers.hearth.test", "display_name": "Inés Okonkwo", "role": "seller"},
    {"email": "jun@makers.hearth.test", "display_name": "Jun Watanabe", "role": "seller"},
    {"email": "lila@makers.hearth.test", "display_name": "Lila Fenn", "role": "seller"},
    # support + admin
    {"email": "support@hearth.test", "display_name": "Hearth Support", "role": "support"},
    {"email": "admin@hearth.test", "display_name": "Hearth Admin", "role": "admin"},
]


# --------------------------------------------------------------------------- catalog
STORES: list[StoreSeed] = [
    {
        "slug": "solveig-ceramics",
        "name": "Sólveig Ceramics",
        "owner_email": "mara@makers.hearth.test",
        "location": "Reykjavík, IS",
        "bio": "Wheel-thrown stoneware fired in small batches. Each piece is glazed by "
        "hand, so no two are exactly alike.",
        "products": [
            {
                "slug": "tide-pour-over-mug",
                "title": "Tide Pour-Over Mug",
                "category": "Kitchen & Dining",
                "description": "A 12oz stoneware mug with a soft matte glaze that pools "
                "deeper at the base, like a receding tide. Comfortable thumb rest, "
                "dishwasher-safe, made to take daily.",
                "attributes": {"material": "stoneware", "capacity_oz": 12, "dishwasher_safe": True},
                "image_url": _img("tide-pour-over-mug", "ceramics"),
                "image_alt": "Hand-thrown matte stoneware mug on a neutral surface",
                "variants": [
                    {
                        "sku": "SOL-MUG-SAGE",
                        "options": {"color": "Sea Sage"},
                        "price_minor": 3400,
                        "qty_on_hand": 24,
                        "qty_reserved": 2,
                        "restock_eta_days": None,
                    },
                    {
                        "sku": "SOL-MUG-ASH",
                        "options": {"color": "Ash Grey"},
                        "price_minor": 3400,
                        "qty_on_hand": 3,  # low stock — interesting for the agent
                        "qty_reserved": 1,
                        "restock_eta_days": 10,
                    },
                ],
                "reviews": [
                    {
                        "author_email": "ada@buyers.hearth.test",
                        "rating": 5,
                        "title": "My everyday mug now",
                        "body": "The glaze is even prettier in person and it keeps coffee "
                        "warm a good while. Reach for it every morning.",
                    },
                    {
                        "author_email": "ben@buyers.hearth.test",
                        "rating": 4,
                        "title": "Lovely, slightly small",
                        "body": "Beautiful piece. Just know 12oz is a touch small if you "
                        "like a big cup.",
                    },
                ],
            },
            {
                "slug": "ebb-serving-bowl",
                "title": "Ebb Serving Bowl",
                "category": "Kitchen & Dining",
                "description": "A wide, shallow serving bowl that makes a salad look like "
                "the main event. Reactive glaze with flecks of iron; food-safe.",
                "attributes": {"material": "stoneware", "diameter_cm": 28, "food_safe": True},
                "image_url": _img("ebb-serving-bowl", "ceramics"),
                "image_alt": "Wide shallow stoneware serving bowl, speckled glaze",
                "variants": [
                    {
                        "sku": "SOL-BOWL-OAT",
                        "options": {"color": "Oat Speckle"},
                        "price_minor": 6800,
                        "qty_on_hand": 11,
                        "qty_reserved": 0,
                        "restock_eta_days": None,
                    },
                ],
                "reviews": [
                    {
                        "author_email": "cora@buyers.hearth.test",
                        "rating": 5,
                        "title": "Gorgeous and sturdy",
                        "body": "Heavier than I expected in the best way. Survives a busy "
                        "kitchen.",
                    },
                ],
            },
            {
                "slug": "drift-dinner-plates",
                "title": "Drift Dinner Plates (Set of 2)",
                "category": "Kitchen & Dining",
                "description": "A pair of wide-rimmed stoneware dinner plates with a soft "
                "speckle and a glaze that breaks lighter at the edge. Stackable, oven- and "
                "dishwasher-safe.",
                "attributes": {"material": "stoneware", "set_size": 2, "diameter_cm": 27},
                "image_url": _img("drift-dinner-plates", "ceramics"),
                "image_alt": "Two speckled stoneware dinner plates stacked",
                "variants": [
                    {
                        "sku": "SOL-PLATE-MIST",
                        "options": {"color": "Sea Mist"},
                        "price_minor": 7600,
                        "qty_on_hand": 14,
                        "qty_reserved": 1,
                        "restock_eta_days": None,
                    },
                ],
                "reviews": [
                    {
                        "author_email": "deepa@buyers.hearth.test",
                        "rating": 5,
                        "title": "Dinner feels special",
                        "body": "The weight and the glaze make a weeknight meal look "
                        "intentional.",
                    },
                ],
            },
            {
                "slug": "kelp-bud-vase",
                "title": "Kelp Bud Vase",
                "category": "Home",
                "description": "A slender hand-thrown bud vase in a deep reactive green, "
                "made for a single stem or a few sprigs of foraged greenery.",
                "attributes": {"material": "stoneware", "height_cm": 16, "watertight": True},
                "image_url": _img("kelp-bud-vase", "ceramics"),
                "image_alt": "Slender deep-green stoneware bud vase",
                "variants": [
                    {
                        "sku": "SOL-VASE-KELP",
                        "options": {"color": "Kelp Green"},
                        "price_minor": 4400,
                        "qty_on_hand": 0,  # out of stock
                        "qty_reserved": 0,
                        "restock_eta_days": 18,
                    },
                ],
                "reviews": [],
            },
        ],
    },
    {
        "slug": "herrera-leather",
        "name": "Herrera Leather Works",
        "owner_email": "tomas@makers.hearth.test",
        "location": "Oaxaca, MX",
        "bio": "Full-grain leather goods, hand-stitched with waxed linen thread. Built "
        "to outlast the trends.",
        "products": [
            {
                "slug": "carryall-card-wallet",
                "title": "Carryall Card Wallet",
                "category": "Accessories",
                "description": "A slim four-pocket card wallet in vegetable-tanned leather "
                "that darkens beautifully with use. Holds 8–10 cards and folded bills.",
                "attributes": {"material": "veg-tan leather", "card_capacity": 10},
                "image_url": _img("carryall-card-wallet", "leather"),
                "image_alt": "Slim hand-stitched leather card wallet",
                "variants": [
                    {
                        "sku": "HER-WAL-TAN",
                        "options": {"color": "Natural Tan"},
                        "price_minor": 5200,
                        "qty_on_hand": 18,
                        "qty_reserved": 1,
                        "restock_eta_days": None,
                    },
                    {
                        "sku": "HER-WAL-ESP",
                        "options": {"color": "Espresso"},
                        "price_minor": 5200,
                        "qty_on_hand": 0,  # out of stock
                        "qty_reserved": 0,
                        "restock_eta_days": 21,
                    },
                ],
                "reviews": [
                    {
                        "author_email": "deepa@buyers.hearth.test",
                        "rating": 5,
                        "title": "Ages like a good pair of boots",
                        "body": "Three months in and the patina is unreal. Stitching is "
                        "dead straight.",
                    },
                    {
                        "author_email": "evan@buyers.hearth.test",
                        "rating": 4,
                        "title": "Stiff at first",
                        "body": "Took a week or two to break in. Worth it.",
                    },
                ],
            },
            {
                "slug": "field-belt",
                "title": "Field Belt",
                "category": "Accessories",
                "description": "A 38mm full-grain belt with a solid brass buckle. Cut and "
                "punched to order, so it actually fits.",
                "attributes": {"material": "full-grain leather", "width_mm": 38, "buckle": "brass"},
                "image_url": _img("field-belt", "leather"),
                "image_alt": "Brown full-grain leather belt with brass buckle",
                "variants": [
                    {
                        "sku": "HER-BELT-32",
                        "options": {"size": '32"'},
                        "price_minor": 7400,
                        "qty_on_hand": 6,
                        "qty_reserved": 0,
                        "restock_eta_days": None,
                    },
                    {
                        "sku": "HER-BELT-34",
                        "options": {"size": '34"'},
                        "price_minor": 7400,
                        "qty_on_hand": 4,
                        "qty_reserved": 1,
                        "restock_eta_days": None,
                    },
                ],
                "reviews": [],
            },
            {
                "slug": "dispatch-leather-tote",
                "title": "Dispatch Leather Tote",
                "category": "Bags",
                "description": "A roomy full-grain tote with riveted handles and a waxed "
                "linen-stitched base. Carries a laptop, a notebook, and the rest of your "
                "day without complaint.",
                "attributes": {"material": "full-grain leather", "fits_laptop_in": 15},
                "image_url": _img("dispatch-leather-tote", "leather"),
                "image_alt": "Tan full-grain leather tote with riveted handles",
                "variants": [
                    {
                        "sku": "HER-TOTE-CHE",
                        "options": {"color": "Chestnut"},
                        "price_minor": 18900,
                        "qty_on_hand": 5,
                        "qty_reserved": 0,
                        "restock_eta_days": None,
                    },
                    {
                        "sku": "HER-TOTE-BLK",
                        "options": {"color": "Black"},
                        "price_minor": 18900,
                        "qty_on_hand": 2,  # low stock
                        "qty_reserved": 0,
                        "restock_eta_days": 12,
                    },
                ],
                "reviews": [
                    {
                        "author_email": "ada@buyers.hearth.test",
                        "rating": 5,
                        "title": "My everyday bag",
                        "body": "Sturdy, holds its shape, and the leather is already "
                        "softening nicely.",
                    },
                ],
            },
            {
                "slug": "keystone-keychain",
                "title": "Keystone Leather Keychain",
                "category": "Accessories",
                "description": "A small hand-stitched leather fob with a solid brass ring. "
                "The kind of little upgrade you notice every time you reach for your keys.",
                "attributes": {"material": "veg-tan leather", "hardware": "brass"},
                "image_url": _img("keystone-keychain", "leather"),
                "image_alt": "Small hand-stitched leather keychain fob",
                "variants": [
                    {
                        "sku": "HER-KEY-TAN",
                        "options": {"color": "Natural Tan"},
                        "price_minor": 1800,
                        "qty_on_hand": 33,
                        "qty_reserved": 2,
                        "restock_eta_days": None,
                    },
                ],
                "reviews": [],
            },
        ],
    },
    {
        "slug": "okonkwo-textiles",
        "name": "Okonkwo Textiles",
        "owner_email": "ines@makers.hearth.test",
        "location": "Lisbon, PT",
        "bio": "Handwoven throws and napkins in naturally dyed cotton and linen. Slow "
        "cloth for a calm home.",
        "products": [
            {
                "slug": "morning-linen-napkins",
                "title": "Morning Linen Napkins (Set of 4)",
                "category": "Home",
                "description": "Stonewashed linen napkins with a hand-knotted fringe. They "
                "get softer every wash and shrug off a spilled glass of wine.",
                "attributes": {"material": "linen", "set_size": 4, "machine_washable": True},
                "image_url": _img("morning-linen-napkins", "textiles"),
                "image_alt": "Folded stonewashed linen napkins",
                "variants": [
                    {
                        "sku": "OKO-NAP-OAT",
                        "options": {"color": "Oatmeal"},
                        "price_minor": 4200,
                        "qty_on_hand": 30,
                        "qty_reserved": 0,
                        "restock_eta_days": None,
                    },
                    {
                        "sku": "OKO-NAP-CLAY",
                        "options": {"color": "Clay"},
                        "price_minor": 4200,
                        "qty_on_hand": 2,  # low stock
                        "qty_reserved": 0,
                        "restock_eta_days": 7,
                    },
                ],
                "reviews": [
                    {
                        "author_email": "ada@buyers.hearth.test",
                        "rating": 5,
                        "title": "Soft and forgiving",
                        "body": "Washed out a red-wine spill completely. Use them daily now, "
                        "not just for company.",
                    },
                ],
            },
            {
                "slug": "harbor-throw",
                "title": "Harbor Throw",
                "category": "Home",
                "description": "A generously sized handwoven cotton throw with a subtle "
                "herringbone weave. Light enough for summer, warm enough for a cool evening.",
                "attributes": {"material": "cotton", "dimensions_cm": "130x180"},
                "image_url": _img("harbor-throw", "textiles"),
                "image_alt": "Folded handwoven cotton throw",
                "variants": [
                    {
                        "sku": "OKO-THROW-HARBOR",
                        "options": {"color": "Harbor Blue"},
                        "price_minor": 9800,
                        "qty_on_hand": 7,
                        "qty_reserved": 1,
                        "restock_eta_days": None,
                    },
                ],
                "reviews": [
                    {
                        "author_email": "cora@buyers.hearth.test",
                        "rating": 4,
                        "title": "Beautiful weave",
                        "body": "Lovely and well made. A bit lighter than I pictured, but "
                        "perfect over the shoulders.",
                    },
                    {
                        "author_email": "deepa@buyers.hearth.test",
                        "rating": 5,
                        "title": "Lives on the sofa",
                        "body": "Exactly the calm, neutral piece I wanted.",
                    },
                ],
            },
            {
                "slug": "dune-wool-blanket",
                "title": "Dune Wool Blanket",
                "category": "Home",
                "description": "A substantial handwoven wool blanket with a wide natural "
                "border. Warm without weight, the one you steal from the foot of the bed on "
                "a cold night.",
                "attributes": {"material": "wool", "dimensions_cm": "150x200"},
                "image_url": _img("dune-wool-blanket", "textiles"),
                "image_alt": "Folded cream wool blanket with a natural border",
                "variants": [
                    {
                        "sku": "OKO-BLANKET-DUNE",
                        "options": {"color": "Dune"},
                        "price_minor": 14500,
                        "qty_on_hand": 6,
                        "qty_reserved": 1,
                        "restock_eta_days": None,
                    },
                    {
                        "sku": "OKO-BLANKET-SLATE",
                        "options": {"color": "Slate"},
                        "price_minor": 14500,
                        "qty_on_hand": 3,  # low stock
                        "qty_reserved": 0,
                        "restock_eta_days": 9,
                    },
                ],
                "reviews": [
                    {
                        "author_email": "evan@buyers.hearth.test",
                        "rating": 5,
                        "title": "Worth every penny",
                        "body": "Heirloom-warm and the weave is flawless. Lives on our bed "
                        "all winter.",
                    },
                ],
            },
            {
                "slug": "field-tea-towels",
                "title": "Field Tea Towels (Set of 2)",
                "category": "Kitchen & Dining",
                "description": "Absorbent waffle-weave linen tea towels with a woven stripe. "
                "They actually dry dishes instead of pushing the water around.",
                "attributes": {"material": "linen", "set_size": 2, "weave": "waffle"},
                "image_url": _img("field-tea-towels", "textiles"),
                "image_alt": "Two striped waffle-weave linen tea towels",
                "variants": [
                    {
                        "sku": "OKO-TOWEL-SAGE",
                        "options": {"color": "Sage Stripe"},
                        "price_minor": 3200,
                        "qty_on_hand": 26,
                        "qty_reserved": 0,
                        "restock_eta_days": None,
                    },
                ],
                "reviews": [],
            },
        ],
    },
    {
        "slug": "watanabe-woodcraft",
        "name": "Watanabe Woodcraft",
        "owner_email": "jun@makers.hearth.test",
        "location": "Takayama, JP",
        "bio": "Hand-carved kitchen tools in cherry and walnut, finished with food-safe "
        "oil. Made to feel right in the hand.",
        "products": [
            {
                "slug": "grain-cutting-board",
                "title": "End-Grain Cutting Board",
                "category": "Kitchen & Dining",
                "description": "A walnut end-grain board that's kind to your knives and "
                "self-heals small cuts. Juice groove on one side, flat prep surface on the "
                "other.",
                "attributes": {"wood": "walnut", "dimensions_cm": "40x28x4", "reversible": True},
                "image_url": _img("grain-cutting-board", "woodwork"),
                "image_alt": "Walnut end-grain cutting board with juice groove",
                "variants": [
                    {
                        "sku": "WAT-BOARD-WAL",
                        "options": {"wood": "Walnut"},
                        "price_minor": 11500,
                        "qty_on_hand": 9,
                        "qty_reserved": 0,
                        "restock_eta_days": None,
                    },
                ],
                "reviews": [
                    {
                        "author_email": "evan@buyers.hearth.test",
                        "rating": 5,
                        "title": "Heirloom quality",
                        "body": "Heavy, flat, and beautiful. Oil it monthly and it glows.",
                    },
                ],
            },
            {
                "slug": "nara-serving-spoons",
                "title": "Nara Serving Spoons (Pair)",
                "category": "Kitchen & Dining",
                "description": "A matched pair of cherry serving spoons, hand-carved with a "
                "comfortable, slightly flattened handle. Won't scratch your good pans.",
                "attributes": {"wood": "cherry", "set_size": 2},
                "image_url": _img("nara-serving-spoons", "woodwork"),
                "image_alt": "Hand-carved wooden serving spoons",
                "variants": [
                    {
                        "sku": "WAT-SPOON-CHERRY",
                        "options": {"wood": "Cherry"},
                        "price_minor": 5600,
                        "qty_on_hand": 1,  # very low stock
                        "qty_reserved": 0,
                        "restock_eta_days": 14,
                    },
                ],
                "reviews": [],
            },
            {
                "slug": "stack-coffee-scoop",
                "title": "Stack Coffee Scoop",
                "category": "Kitchen & Dining",
                "description": "A hand-carved walnut coffee scoop that holds a level two "
                "tablespoons. Smooth enough to live in the bean jar, pretty enough to leave "
                "on the counter.",
                "attributes": {"wood": "walnut", "capacity_tbsp": 2},
                "image_url": _img("stack-coffee-scoop", "woodwork"),
                "image_alt": "Hand-carved walnut coffee scoop",
                "variants": [
                    {
                        "sku": "WAT-SCOOP-WAL",
                        "options": {"wood": "Walnut"},
                        "price_minor": 2400,
                        "qty_on_hand": 19,
                        "qty_reserved": 0,
                        "restock_eta_days": None,
                    },
                ],
                "reviews": [
                    {
                        "author_email": "ben@buyers.hearth.test",
                        "rating": 4,
                        "title": "Small and lovely",
                        "body": "Does exactly one thing and does it beautifully. Nice gift.",
                    },
                ],
            },
            {
                "slug": "ridge-walnut-tray",
                "title": "Ridge Walnut Catch-All Tray",
                "category": "Home",
                "description": "A low hand-finished walnut tray for keys, coins, and the "
                "small things that pile up by the door. Felt-footed so it won't scratch.",
                "attributes": {"wood": "walnut", "dimensions_cm": "22x14x2"},
                "image_url": _img("ridge-walnut-tray", "woodwork"),
                "image_alt": "Low hand-finished walnut catch-all tray",
                "variants": [
                    {
                        "sku": "WAT-TRAY-WAL",
                        "options": {"wood": "Walnut"},
                        "price_minor": 4900,
                        "qty_on_hand": 8,
                        "qty_reserved": 1,
                        "restock_eta_days": None,
                    },
                ],
                "reviews": [],
            },
        ],
    },
    {
        "slug": "fenn-apothecary",
        "name": "Fenn Apothecary",
        "owner_email": "lila@makers.hearth.test",
        "location": "Portland, US",
        "bio": "Small-batch soy candles and balms scented with essential oils. No synthetic "
        "fragrance, ever.",
        "products": [
            {
                "slug": "hearthlight-candle",
                "title": "Hearthlight Soy Candle",
                "category": "Home",
                "description": "A 9oz soy candle in cedar, amber, and a whisper of smoke — "
                "like a fire two rooms away. Burns clean for about 50 hours.",
                "attributes": {"wax": "soy", "burn_hours": 50, "scent": "cedar & amber"},
                "image_url": _img("hearthlight-candle", "candle"),
                "image_alt": "Poured soy candle in a glass vessel",
                "variants": [
                    {
                        "sku": "FEN-CANDLE-CEDAR",
                        "options": {"scent": "Cedar & Amber"},
                        "price_minor": 2800,
                        "qty_on_hand": 40,
                        "qty_reserved": 3,
                        "restock_eta_days": None,
                    },
                    {
                        "sku": "FEN-CANDLE-FIG",
                        "options": {"scent": "Wild Fig"},
                        "price_minor": 2800,
                        "qty_on_hand": 5,  # low stock
                        "qty_reserved": 0,
                        "restock_eta_days": 5,
                    },
                ],
                "reviews": [
                    {
                        "author_email": "ben@buyers.hearth.test",
                        "rating": 5,
                        "title": "Cozy without being sweet",
                        "body": "Finally a cedar candle that smells like actual wood. Throw "
                        "is great even unlit.",
                    },
                    {
                        "author_email": "ada@buyers.hearth.test",
                        "rating": 4,
                        "title": "Lovely scent, even burn",
                        "body": "Burns evenly to the edge. Wish it lasted a little longer.",
                    },
                ],
            },
            {
                "slug": "salve-hand-balm",
                "title": "Salve Hand Balm",
                "category": "Bath & Body",
                "description": "A non-greasy beeswax and shea balm for hands that have done "
                "real work. Light calendula scent, absorbs fast.",
                "attributes": {"base": "beeswax & shea", "size_ml": 60, "synthetic_free": True},
                "image_url": _img("salve-hand-balm", "balm"),
                "image_alt": "Small tin of natural hand balm",
                "variants": [
                    {
                        "sku": "FEN-BALM-CAL",
                        "options": {"scent": "Calendula"},
                        "price_minor": 1900,
                        "qty_on_hand": 22,
                        "qty_reserved": 0,
                        "restock_eta_days": None,
                    },
                ],
                "reviews": [
                    {
                        "author_email": "deepa@buyers.hearth.test",
                        "rating": 5,
                        "title": "Saved my winter hands",
                        "body": "Not greasy at all and a little goes a long way.",
                    },
                ],
            },
        ],
    },
]


# --------------------------------------------------------------------------- policies
# Platform-level policies (store_slug=None) + a couple of store-specific overrides.
# Written as genuine, quotable prose — this is the support agent's RAG source.
POLICIES: list[PolicySeed] = [
    {
        "store_slug": None,
        "kind": "returns",
        "title": "Hearth Returns Policy",
        "body": (
            "You can return most items within 30 days of delivery for a full refund to "
            "your original payment method. Items must be unused and in their original "
            "condition. To start a return, open the order and choose 'Return items' — "
            "we'll email a prepaid shipping label. Refunds are issued within 5 business "
            "days of the item arriving back at the maker. A few things can't be returned: "
            "personalized or made-to-order pieces, and bath & body products that have been "
            "opened, for hygiene reasons. If something arrived damaged or wasn't what you "
            "ordered, contact support within 14 days and we'll make it right at no cost to "
            "you."
        ),
    },
    {
        "store_slug": None,
        "kind": "shipping",
        "title": "Hearth Shipping & Delivery",
        "body": (
            "Most makers ship within 2 business days. Standard delivery within the "
            "continental US takes 3–7 business days; international orders typically take "
            "7–21 business days depending on customs. Shipping is free on orders over $75; "
            "below that, a flat $6 applies. Made-to-order items (like cut-to-size belts) "
            "ship on the timeline shown on the product page. You'll get a tracking link by "
            "email as soon as your order leaves the studio."
        ),
    },
    {
        "store_slug": None,
        "kind": "payments",
        "title": "Payments & Pricing",
        "body": (
            "We accept all major credit and debit cards. Prices are shown in US dollars and "
            "include applicable taxes at checkout. Your card is charged when the order is "
            "placed. If an item is made to order, you're charged at purchase and the maker "
            "begins work right away. We never store your full card number on our servers."
        ),
    },
    {
        "store_slug": None,
        "kind": "platform",
        "title": "About Hearth & Our Makers",
        "body": (
            "Hearth is a marketplace for independent makers. Every item is made or "
            "finished by hand by the seller listed on the product page, and the maker keeps "
            "the large majority of each sale. We vet new sellers for quality and honesty, "
            "and we ask makers to describe their goods plainly — what it's made of, how "
            "big it is, and how to care for it. If a listing is ever inaccurate, tell us "
            "and we'll fix it."
        ),
    },
    {
        "store_slug": "solveig-ceramics",
        "kind": "care",
        "title": "Caring for Your Stoneware",
        "body": (
            "Sólveig stoneware is dishwasher- and microwave-safe, but it'll keep its glaze "
            "looking best with the occasional hand wash. Avoid sudden temperature changes — "
            "don't take a piece from the freezer straight to a hot oven. Small variations "
            "in glaze and the odd tiny iron speck are normal marks of a handmade piece, not "
            "defects."
        ),
    },
    {
        "store_slug": "herrera-leather",
        "kind": "returns",
        "title": "Herrera Leather — Made-to-Order Returns",
        "body": (
            "Stock items (card wallets, in-stock belt sizes) follow Hearth's standard "
            "30-day return policy. Belts cut to a custom size are made to order and can't "
            "be returned unless they arrive faulty — please double-check your measurement "
            "before ordering. If a custom belt arrives with a defect, we'll remake or "
            "refund it; just reach out within 14 days with a photo."
        ),
    },
    {
        "store_slug": "fenn-apothecary",
        "kind": "care",
        "title": "Candle & Balm Care",
        "body": (
            "For the cleanest burn, trim your candle's wick to about 5mm before each light "
            "and let the first burn reach the edge of the glass (about 2 hours) so it won't "
            "tunnel. Keep balms below 25°C so they don't soften. Our bath & body products "
            "can't be returned once opened, for hygiene reasons — but if something's wrong "
            "with your order, contact us within 14 days."
        ),
    },
]
