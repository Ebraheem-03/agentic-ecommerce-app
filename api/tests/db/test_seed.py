"""Seed proof on a fresh migrated DB (US-E3-03).

Reuses the Day-4 ``migration_db`` throwaway-DB fixture: migrate to head, run the seed
through the ORM, and assert:

1. Row counts are > 0 across the must-have entities (users/stores/products/variants/
   inventory/policies/embeddings) and users span all four roles.
2. Every ``embeddings.embedding`` has length == ``settings.embed_dim`` (the dimension
   contract Echo's real embedder must keep).
3. Running the seed a SECOND time leaves counts unchanged (idempotent upserts).
4. The derived ``products.rating_avg/rating_count`` rollup is recomputed from reviews.
"""

from __future__ import annotations

import importlib

from alembic.config import Config
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session

import app.core.config as app_config
from alembic import command
from app.db.models import (
    Embedding,
    Inventory,
    Policy,
    Product,
    Store,
    User,
    Variant,
)
from app.db.seed.run import seed

MUST_HAVE = ("users", "stores", "products", "variants", "inventory", "policies", "embeddings")


def _sqla_url(dsn: str) -> str:
    return make_url(dsn).set(drivername="postgresql+psycopg").render_as_string(
        hide_password=False
    )


def test_seed_populates_and_is_idempotent(migration_db: tuple[Config, str]) -> None:
    cfg, dsn = migration_db
    command.upgrade(cfg, "head")
    importlib.reload(app_config)
    embed_dim = app_config.settings.embed_dim

    engine = create_engine(_sqla_url(dsn), future=True)
    try:
        # --- first seed ---
        with Session(engine) as s:
            counts = seed(s)
            s.commit()

        for key in MUST_HAVE:
            assert counts[key] > 0, f"{key} not seeded"

        with Session(engine) as s:
            # All four user roles present.
            roles = set(s.scalars(select(User.role).distinct()))
            assert roles == {"buyer", "seller", "support", "admin"}

            # Every embedding vector is exactly settings.embed_dim long. vector_dims()
            # is the pgvector function for a vector column's dimensionality.
            dims = set(
                s.scalars(select(func.vector_dims(Embedding.embedding)).distinct())
            )
            assert dims == {embed_dim}, f"embedding dims != {embed_dim}: {dims}"

            # Embeddings cover both source types.
            src_types = set(s.scalars(select(Embedding.source_type).distinct()))
            assert src_types == {"product", "policy"}

            # Derived rollup recomputed: a product with reviews has avg/count set.
            mug = s.scalar(select(Product).where(Product.slug == "tide-pour-over-mug"))
            assert mug is not None
            assert mug.rating_count == 2
            assert mug.rating_avg == 4.5

            # Inventory has at least one low-stock row (makes agent answers interesting).
            low = s.scalar(
                select(func.count())
                .select_from(Inventory)
                .where(Inventory.qty_on_hand <= 3)
            )
            assert (low or 0) >= 1

            first_counts = _live_counts(s)

        # --- second seed: must not duplicate or error ---
        with Session(engine) as s:
            seed(s)
            s.commit()
        with Session(engine) as s:
            assert _live_counts(s) == first_counts
    finally:
        engine.dispose()


def _live_counts(s: Session) -> dict[str, int]:
    def n(model: type) -> int:
        return s.scalar(select(func.count()).select_from(model)) or 0

    return {
        "users": n(User),
        "stores": n(Store),
        "products": n(Product),
        "variants": n(Variant),
        "inventory": n(Inventory),
        "policies": n(Policy),
        "embeddings": n(Embedding),
    }
