"""Round-trip insert/select through the ORM against a migrated DB (US-E3-04).

Proves the mapped models actually write and read: server-side uuidv7 + now()
defaults populate, native enums accept their labels, and a pgvector ``embeddings``
row at ``settings.embed_dim`` inserts and reads back at full length.
"""

from __future__ import annotations

import importlib

from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session

import app.core.config as app_config
from alembic import command
from app.db.models import (
    Embedding,
    Inventory,
    Product,
    Store,
    User,
    Variant,
)


def _sqla_url(dsn: str) -> str:
    return make_url(dsn).set(drivername="postgresql+psycopg").render_as_string(
        hide_password=False
    )


def test_core_roundtrip(migration_db: tuple[Config, str]) -> None:
    cfg, dsn = migration_db
    command.upgrade(cfg, "head")
    importlib.reload(app_config)
    embed_dim = app_config.settings.embed_dim

    engine = create_engine(_sqla_url(dsn), future=True)
    try:
        with Session(engine) as s:
            user = User(
                email="parity@hearth.test",
                display_name="Parity Tester",
                role="seller",
            )
            s.add(user)
            s.flush()
            # Server defaults populated after flush.
            assert user.id is not None
            assert user.is_active is True
            assert user.created_at is not None

            store = Store(
                owner_id=user.id,
                name="Parity Store",
                slug="parity-store",
                status="active",
            )
            s.add(store)
            s.flush()

            product = Product(
                store_id=store.id,
                title="Parity Mug",
                slug="parity-mug",
                description="A mug for testing.",
                status="active",
                attributes={"material": "stoneware"},
            )
            s.add(product)
            s.flush()
            # jsonb server default + explicit value round-trip.
            assert product.attributes == {"material": "stoneware"}
            assert product.rating_count == 0

            variant = Variant(
                product_id=product.id,
                sku="PARITY-MUG-01",
                options={"color": "sage"},
                price_minor=2400,
            )
            s.add(variant)
            s.flush()
            assert variant.currency == "USD"
            assert variant.is_active is True

            inv = Inventory(variant_id=variant.id, qty_on_hand=5, restock_eta_days=3)
            s.add(inv)
            s.flush()

            vec = [0.01] * embed_dim
            emb = Embedding(
                source_type="product",
                source_id=product.id,
                chunk_text="Parity Mug — stoneware, sage.",
                chunk_index=0,
                embedding=vec,
                model="seed-stub",
            )
            s.add(emb)
            s.commit()

        # Fresh session: read everything back.
        with Session(engine) as s:
            got_user = s.scalar(select(User).where(User.email == "parity@hearth.test"))
            assert got_user is not None
            assert got_user.role == "seller"

            got_emb = s.scalar(select(Embedding).where(Embedding.model == "seed-stub"))
            assert got_emb is not None
            assert got_emb.source_type == "product"
            assert len(list(got_emb.embedding)) == embed_dim
    finally:
        engine.dispose()
