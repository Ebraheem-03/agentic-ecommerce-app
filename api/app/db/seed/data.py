"""The Hearth seed content — believable artisan/maker marketplace (US-E3-03).

Pure data (no DB calls). Natural keys (email, slug, sku, order_number) drive the
idempotent upserts in ``run.py``. Voice follows the brand brief: warm, plain-spoken,
honest. Policy bodies are written as genuine, quotable prose — they are the RAG
source the support agent retrieves over (feeds US-QA-D05 golden answers), so return
windows / shipping times / etc. are concrete.
"""

from __future__ import annotations

from typing import Any, TypedDict


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
                "image_url": "https://images.hearth.test/solveig/tide-mug.jpg",
                "image_alt": "Matte sage stoneware mug with a pooled glaze base",
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
                "image_url": "https://images.hearth.test/solveig/ebb-bowl.jpg",
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
                "image_url": "https://images.hearth.test/herrera/card-wallet.jpg",
                "image_alt": "Slim tan leather card wallet, hand-stitched edges",
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
                "image_url": "https://images.hearth.test/herrera/field-belt.jpg",
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
                "image_url": "https://images.hearth.test/okonkwo/linen-napkins.jpg",
                "image_alt": "Folded set of four oat-colored linen napkins with fringe",
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
                "image_url": "https://images.hearth.test/okonkwo/harbor-throw.jpg",
                "image_alt": "Folded blue-and-cream herringbone cotton throw",
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
                "image_url": "https://images.hearth.test/watanabe/cutting-board.jpg",
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
                "image_url": "https://images.hearth.test/watanabe/serving-spoons.jpg",
                "image_alt": "Pair of hand-carved cherry serving spoons",
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
                "image_url": "https://images.hearth.test/fenn/hearthlight-candle.jpg",
                "image_alt": "Amber glass soy candle with a kraft label",
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
                "image_url": "https://images.hearth.test/fenn/hand-balm.jpg",
                "image_alt": "Small tin of pale yellow hand balm, open",
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
