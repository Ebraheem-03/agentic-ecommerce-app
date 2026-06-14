"""Idempotent seed orchestration for the Hearth marketplace (US-E3-03).

Writes the content from ``data.py`` through the Story-1 ORM models, computes the
``products.rating_avg/rating_count`` rollups, and generates ``embeddings`` rows for
products and policies through the pluggable embedding provider seam in
``app.services.embeddings`` (``refresh_product_embedding`` for products; the same
``upsert_embedding`` for policies). The active provider defaults to the deterministic
``StubEmbedder``; Echo swaps in a real model via ``EMBED_PROVIDER`` (ADR-0026).

IDEMPOTENT by design: every entity is upserted on its natural key (user email-live,
store slug, product slug, variant sku, embedding (source_type, source_id, chunk_index)),
so ``python -m app.db.seed`` can run any number of times — and after ``db_reset.sh`` —
without duplicating rows or erroring. Re-running updates mutable fields in place.
"""

from __future__ import annotations

import os
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import (
    Embedding,
    Inventory,
    Policy,
    Product,
    ProductImage,
    Review,
    Store,
    User,
    Variant,
)
from app.db.seed import data
from app.db.session import session_scope
from app.services.embeddings import (
    Embedder,
    get_embedder,
    refresh_product_embedding,
    upsert_embedding,
)

# Single deterministic test-mode password for every seeded persona. Env-derived so no
# literal credential is committed (GitGuardian scans full history) — the default MUST
# match tests/fixtures/handles.py so all three test layers log in identically (ADR-0023).
TEST_PASSWORD = os.environ.get("HEARTH_TEST_PASSWORD", "CHANGE_ME_test_pw")


def _get_user(s: Session, email: str) -> User | None:
    return s.scalar(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )


def _upsert_users(s: Session) -> dict[str, User]:
    """Idempotently upsert seed personas WITH auth credentials (US-E4-04).

    Every persona gets an argon2id hash of ``TEST_PASSWORD`` and ``email_verified=True``
    so they can log in past the verification gate. Re-running refreshes the hash/flag in
    place (a fresh argon2 salt each run is fine — verification still succeeds) without
    duplicating rows.
    """
    by_email: dict[str, User] = {}
    for u in data.USERS:
        existing = _get_user(s, u["email"])
        if existing is None:
            existing = User(email=u["email"], display_name=u["display_name"], role=u["role"])
            s.add(existing)
        else:
            existing.display_name = u["display_name"]
            existing.role = u["role"]
        existing.password_hash = hash_password(TEST_PASSWORD)
        existing.email_verified = True
        by_email[u["email"]] = existing
    s.flush()
    return by_email


def _upsert_store(s: Session, store: data.StoreSeed, owner: User) -> Store:
    existing = s.scalar(select(Store).where(Store.slug == store["slug"]))
    if existing is None:
        existing = Store(slug=store["slug"], owner_id=owner.id)
        s.add(existing)
    existing.name = store["name"]
    existing.owner_id = owner.id
    existing.location = store["location"]
    existing.bio = store["bio"]
    existing.status = "active"
    s.flush()
    return existing


def _upsert_product(s: Session, store: Store, prod: data.ProductSeed) -> Product:
    existing = s.scalar(select(Product).where(Product.slug == prod["slug"]))
    if existing is None:
        existing = Product(slug=prod["slug"], store_id=store.id)
        s.add(existing)
    existing.store_id = store.id
    existing.title = prod["title"]
    existing.category = prod["category"]
    existing.description = prod["description"]
    existing.attributes = prod["attributes"]
    existing.status = "active"
    s.flush()
    return existing


def _upsert_variant(s: Session, product: Product, v: data.VariantSeed) -> Variant:
    existing = s.scalar(select(Variant).where(Variant.sku == v["sku"]))
    if existing is None:
        existing = Variant(sku=v["sku"], product_id=product.id)
        s.add(existing)
    existing.product_id = product.id
    existing.options = v["options"]
    existing.price_minor = v["price_minor"]
    existing.currency = "USD"
    existing.is_active = True
    s.flush()
    return existing


def _upsert_inventory(s: Session, variant: Variant, v: data.VariantSeed) -> None:
    existing = s.scalar(select(Inventory).where(Inventory.variant_id == variant.id))
    if existing is None:
        existing = Inventory(variant_id=variant.id)
        s.add(existing)
    existing.qty_on_hand = v["qty_on_hand"]
    existing.qty_reserved = v["qty_reserved"]
    existing.restock_eta_days = v["restock_eta_days"]


def _upsert_image(s: Session, product: Product, prod: data.ProductSeed) -> None:
    # One primary image per product (position 0). Match on (product, position).
    existing = s.scalar(
        select(ProductImage).where(
            ProductImage.product_id == product.id, ProductImage.position == 0
        )
    )
    if existing is None:
        existing = ProductImage(product_id=product.id, position=0)
        s.add(existing)
    existing.url = prod["image_url"]
    existing.alt = prod["image_alt"]


def _upsert_reviews(s: Session, product: Product, prod: data.ProductSeed) -> None:
    """Upsert reviews on the (product, user) natural key, then roll up the rating."""
    for r in prod["reviews"]:
        author = _get_user(s, r["author_email"])
        if author is None:
            continue
        existing = s.scalar(
            select(Review).where(
                Review.product_id == product.id, Review.user_id == author.id
            )
        )
        if existing is None:
            existing = Review(product_id=product.id, user_id=author.id)
            s.add(existing)
        existing.rating = r["rating"]
        existing.title = r["title"]
        existing.body = r["body"]
    s.flush()

    # Recompute the DERIVED rollups from the actual review rows now in the DB.
    ratings = list(
        s.scalars(select(Review.rating).where(Review.product_id == product.id))
    )
    product.rating_count = len(ratings)
    if ratings:
        avg = Decimal(sum(ratings)) / Decimal(len(ratings))
        product.rating_avg = float(avg.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
    else:
        product.rating_avg = None
    s.flush()


def _upsert_policy(s: Session, p: data.PolicySeed, stores: dict[str, Store]) -> Policy:
    store_id = stores[p["store_slug"]].id if p["store_slug"] is not None else None
    # Natural key: (store_id, kind, title). Platform policies have store_id NULL.
    stmt = select(Policy).where(Policy.kind == p["kind"], Policy.title == p["title"])
    stmt = stmt.where(Policy.store_id == store_id) if store_id is not None else stmt.where(
        Policy.store_id.is_(None)
    )
    existing = s.scalar(stmt)
    if existing is None:
        existing = Policy(kind=p["kind"], title=p["title"], store_id=store_id)
        s.add(existing)
    existing.store_id = store_id
    existing.body = p["body"]
    existing.is_active = True
    s.flush()
    return existing


def seed(session: Session) -> dict[str, int]:
    """Run the full idempotent seed within ``session``; return inserted/updated counts.

    Embeddings go through the same provider seam future write handlers use: products via
    ``refresh_product_embedding`` (rebuilds the doc from the persisted product), policies
    via ``upsert_embedding``. One ``Embedder`` instance is shared across the run.
    """
    embedder: Embedder = get_embedder()
    users = _upsert_users(session)
    stores: dict[str, Store] = {}

    for store_seed in data.STORES:
        owner = users[store_seed["owner_email"]]
        store = _upsert_store(session, store_seed, owner)
        stores[store_seed["slug"]] = store

        for prod_seed in store_seed["products"]:
            product = _upsert_product(session, store, prod_seed)
            for v in prod_seed["variants"]:
                variant = _upsert_variant(session, product, v)
                _upsert_inventory(session, variant, v)
            _upsert_image(session, product, prod_seed)
            _upsert_reviews(session, product, prod_seed)
            session.flush()

            # Product embedding: rebuilt from the persisted product (title/description/
            # category/attributes/variants) via the reusable refresh path.
            refresh_product_embedding(session, product.id, embedder=embedder)

    for policy_seed in data.POLICIES:
        policy = _upsert_policy(session, policy_seed, stores)
        # Policy embedding: one chunk of title + body (the RAG retrieval unit).
        upsert_embedding(
            session,
            source_type="policy",
            source_id=policy.id,
            chunk_index=0,
            text=f"{policy.title}\n{policy.body}",
            embedder=embedder,
        )

    session.flush()
    return _counts(session)


def _counts(s: Session) -> dict[str, int]:
    from sqlalchemy import func

    def n(model: type) -> int:
        return s.scalar(select(func.count()).select_from(model)) or 0

    return {
        "users": n(User),
        "stores": n(Store),
        "products": n(Product),
        "variants": n(Variant),
        "inventory": n(Inventory),
        "reviews": n(Review),
        "policies": n(Policy),
        "embeddings": n(Embedding),
    }


def main() -> None:
    """Entrypoint for ``python -m app.db.seed``."""
    with session_scope() as session:
        counts = seed(session)
    summary = ", ".join(f"{k}={v}" for k, v in counts.items())
    print(f"Hearth seed complete (idempotent). Row counts: {summary}")


if __name__ == "__main__":
    main()
