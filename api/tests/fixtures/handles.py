"""The canonical fixture catalog — stable handles the 3 test layers pin to.

US-QA-D06. Every handle here is a *reference into the seed* (`app.db.seed.data`),
never a duplicate of seed content. We deliberately import the seed module and pull
the live values (emails, slugs, skus, policy kinds, prices, stock) out of it, so:

  * there is exactly ONE place the data lives (the seed), and
  * a handle that names a row the seed no longer has will fail the spine test.

A "handle" = a stable, human-meaningful id (e.g. ``buyer_primary``,
``mug_low_stock``) plus the natural key the seed/contract resolves it by
(email / slug / sku / policy-kind) and the salient facts a test asserts on.

Passwords: the seed (`data.py`) carries no passwords — it provisions identities
only, and Week-2 auth handlers will own credential storage. For the fixture
contract we pin a single deterministic test password per persona here; when the
real ``/auth/register``-backed seeding lands, these are the credentials it must
write. Until then the ``persona_client`` fixture xfails on login (see conftest).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from app.db.seed import data
from app.schemas.enums import ReturnReason, UserRole

# A single deterministic password for every seeded persona in test-mode. Not a
# secret (test data only); kept here so all three layers log in identically.
# Env-derived so no literal credential is committed (GitGuardian scans full
# history): override with HEARTH_TEST_PASSWORD; the default is an obvious
# placeholder. Regenerate the manifest after changing this default.
TEST_PASSWORD = os.environ.get("HEARTH_TEST_PASSWORD", "CHANGE_ME_test_pw")


@dataclass(frozen=True, slots=True)
class Persona:
    """A named account handle resolved by email against the seed ``USERS``."""

    handle: str
    email: str
    display_name: str
    role: UserRole
    password: str = TEST_PASSWORD


@dataclass(frozen=True, slots=True)
class ProductHandle:
    """A named product resolved by slug against the seed catalog."""

    handle: str
    slug: str
    title: str
    store_slug: str


@dataclass(frozen=True, slots=True)
class VariantHandle:
    """A named variant/SKU resolved by sku, carrying the stock fact a test pins to."""

    handle: str
    sku: str
    product_slug: str
    price_minor: int
    qty_on_hand: int
    restock_eta_days: int | None

    @property
    def in_stock(self) -> bool:
        return self.qty_on_hand > 0


@dataclass(frozen=True, slots=True)
class PolicyHandle:
    """A named policy resolved by (kind, store_slug). ``store_slug=None`` = platform.

    ``key`` mirrors the golden dataset's ``<kind>@<store|platform>`` convention so the
    agent layer resolves policies by the exact same string the eval set uses.
    """

    handle: str
    kind: str
    store_slug: str | None
    title: str

    @property
    def key(self) -> str:
        scope = self.store_slug if self.store_slug is not None else "platform"
        return f"{self.kind}@{scope}"


# --------------------------------------------------------------------------- #
# Small lookups into the seed so handles carry live values, not copies.        #
# --------------------------------------------------------------------------- #
def _user(email: str) -> data.UserSeed:
    for u in data.USERS:
        if u["email"] == email:
            return u
    raise KeyError(f"seed has no user {email!r} — handle is stale")


def _flat_products() -> dict[str, tuple[str, data.ProductSeed]]:
    """slug -> (store_slug, product seed)."""
    out: dict[str, tuple[str, data.ProductSeed]] = {}
    for store in data.STORES:
        for prod in store["products"]:
            out[prod["slug"]] = (store["slug"], prod)
    return out


def _flat_variants() -> dict[str, tuple[str, data.VariantSeed]]:
    """sku -> (product_slug, variant seed)."""
    out: dict[str, tuple[str, data.VariantSeed]] = {}
    for _store_slug, prod in _flat_products().values():
        for v in prod["variants"]:
            out[v["sku"]] = (prod["slug"], v)
    return out


def _persona(handle: str, email: str) -> Persona:
    u = _user(email)
    return Persona(
        handle=handle,
        email=u["email"],
        display_name=u["display_name"],
        role=UserRole(u["role"]),
    )


def _product(handle: str, slug: str) -> ProductHandle:
    store_slug, prod = _flat_products()[slug]
    return ProductHandle(handle=handle, slug=slug, title=prod["title"], store_slug=store_slug)


def _variant(handle: str, sku: str) -> VariantHandle:
    product_slug, v = _flat_variants()[sku]
    return VariantHandle(
        handle=handle,
        sku=sku,
        product_slug=product_slug,
        price_minor=v["price_minor"],
        qty_on_hand=v["qty_on_hand"],
        restock_eta_days=v["restock_eta_days"],
    )


def _policy(handle: str, kind: str, store_slug: str | None) -> PolicyHandle:
    for p in data.POLICIES:
        if p["kind"] == kind and p["store_slug"] == store_slug:
            return PolicyHandle(handle=handle, kind=kind, store_slug=store_slug, title=p["title"])
    raise KeyError(f"seed has no policy ({kind!r}, {store_slug!r}) — handle is stale")


# --------------------------------------------------------------------------- #
# THE CANONICAL CATALOG. One entry per stable handle the journeys pin to.       #
# --------------------------------------------------------------------------- #

# Personas — one per role, plus a second buyer for isolation-needing journeys.
PERSONAS: dict[str, Persona] = {
    "buyer_primary": _persona("buyer_primary", "ada@buyers.hearth.test"),
    "buyer_secondary": _persona("buyer_secondary", "ben@buyers.hearth.test"),
    "seller_ceramics": _persona("seller_ceramics", "mara@makers.hearth.test"),
    "seller_leather": _persona("seller_leather", "tomas@makers.hearth.test"),
    "support": _persona("support", "support@hearth.test"),
    "admin": _persona("admin", "admin@hearth.test"),
}

# Products — pinned where a journey references one by name.
PRODUCT_HANDLES: dict[str, ProductHandle] = {
    "mug": _product("mug", "tide-pour-over-mug"),  # the canonical search/compare target
    "card_wallet": _product("card_wallet", "carryall-card-wallet"),  # has an OOS variant
    "belt": _product("belt", "field-belt"),  # made-to-order returns edge
}

# Variants — chosen to span the inventory edge states the journeys need.
VARIANT_HANDLES: dict[str, VariantHandle] = {
    "mug_in_stock": _variant("mug_in_stock", "SOL-MUG-SAGE"),  # qty 24 — happy add-to-cart
    "mug_low_stock": _variant("mug_low_stock", "SOL-MUG-ASH"),  # qty 3 — low-stock agent answer
    "wallet_oos": _variant("wallet_oos", "HER-WAL-ESP"),  # qty 0 — out_of_stock path (J-BUY-03)
    "wallet_in_stock": _variant("wallet_in_stock", "HER-WAL-TAN"),  # qty 18 — buyable wallet
}

# Policies — the RAG/return surfaces. ``key`` matches the golden set's '<kind>@<scope>'.
POLICY_HANDLES: dict[str, PolicyHandle] = {
    "returns_platform": _policy("returns_platform", "returns", None),
    "shipping_platform": _policy("shipping_platform", "shipping", None),
    "payments_platform": _policy("payments_platform", "payments", None),
    "returns_leather": _policy("returns_leather", "returns", "herrera-leather"),
    "care_ceramics": _policy("care_ceramics", "care", "solveig-ceramics"),
}

# Return reasons the J-BUY-06 / J-SUP-03 return + HITL journeys exercise. Mirrors the
# ReturnReason enum exactly (single source: app.schemas.enums).
RETURN_REASONS: tuple[ReturnReason, ...] = tuple(ReturnReason)


@dataclass(frozen=True, slots=True)
class PaymentTestMode:
    """The deterministic test-mode payment switch (contract-v0 §6, ADR-0021).

    Confirm with ``capture_outcome`` for success, ``decline_outcome`` to force a
    402 ``payment_declined``. Purely a function of the request body — no magic
    amount, env flag, or randomness — so J-BUY-04's decline path is stable.
    """

    capture_outcome: str = "captured"
    decline_outcome: str = "failed"
    declined_error_code: str = "payment_declined"
    declined_http_status: int = 402


PAYMENT_TEST_MODE = PaymentTestMode()
