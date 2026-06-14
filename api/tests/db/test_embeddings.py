"""Embedding provider seam + refresh-on-change proof (US-E4-08).

Reuses the Day-4 ``migration_db`` throwaway-DB fixture: migrate to head, seed, then:

1. Every seeded embedding is length == ``settings.embed_dim`` and tagged with the active
   provider's ``model`` (the default ``StubEmbedder`` -> ``"seed-stub"``).
2. ``refresh_product_embedding`` is the live refresh path: mutating a product's source
   text and refreshing CHANGES the stored vector (content-derived), while keeping the
   dimension contract. Re-refreshing with unchanged text leaves the vector identical
   (deterministic / idempotent) and creates no extra row.
"""

from __future__ import annotations

import importlib

from alembic.config import Config
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session

import app.core.config as app_config
from alembic import command
from app.db.models import Embedding, Product
from app.db.seed.run import seed
from app.services.embeddings import (
    SEED_STUB_MODEL,
    build_product_document,
    get_embedder,
    refresh_product_embedding,
)


def _sqla_url(dsn: str) -> str:
    return (
        make_url(dsn).set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
    )


def _product_vector(s: Session, product_id: str) -> list[float]:
    row = s.scalar(
        select(Embedding).where(
            Embedding.source_type == "product",
            Embedding.source_id == product_id,
            Embedding.chunk_index == 0,
        )
    )
    assert row is not None, "product embedding missing"
    return list(row.embedding)


def test_seed_embeddings_tagged_and_sized(migration_db: tuple[Config, str]) -> None:
    cfg, dsn = migration_db
    command.upgrade(cfg, "head")
    importlib.reload(app_config)
    embed_dim = app_config.settings.embed_dim
    expected_model = get_embedder().model
    assert expected_model == SEED_STUB_MODEL  # default provider is the stub

    engine = create_engine(_sqla_url(dsn), future=True)
    try:
        with Session(engine) as s:
            seed(s)
            s.commit()

        with Session(engine) as s:
            dims = set(s.scalars(select(func.vector_dims(Embedding.embedding)).distinct()))
            assert dims == {embed_dim}, f"embedding dims != {embed_dim}: {dims}"
            models = set(s.scalars(select(Embedding.model).distinct()))
            assert models == {expected_model}, f"unexpected model tags: {models}"
    finally:
        engine.dispose()


def test_refresh_changes_vector_on_text_change(migration_db: tuple[Config, str]) -> None:
    """Mutate a product's text -> refresh -> vector changes; same text -> identical."""
    cfg, dsn = migration_db
    command.upgrade(cfg, "head")
    importlib.reload(app_config)
    embed_dim = app_config.settings.embed_dim

    engine = create_engine(_sqla_url(dsn), future=True)
    try:
        with Session(engine) as s:
            seed(s)
            s.commit()

        with Session(engine) as s:
            product = s.scalar(select(Product).where(Product.slug == "tide-pour-over-mug"))
            assert product is not None
            pid = product.id

        with Session(engine) as s:
            before = _product_vector(s, pid)
            assert len(before) == embed_dim

        # --- refresh with UNCHANGED content: vector identical, no new row ---
        with Session(engine) as s:
            n_before = s.scalar(select(func.count()).select_from(Embedding)) or 0
            refresh_product_embedding(s, pid)
            s.commit()
        with Session(engine) as s:
            unchanged = _product_vector(s, pid)
            n_after = s.scalar(select(func.count()).select_from(Embedding)) or 0
        assert unchanged == before, "deterministic refresh must reproduce the vector"
        assert n_after == n_before, "refresh must upsert, not insert a duplicate"

        # --- mutate product text, then refresh: vector must change ---
        with Session(engine) as s:
            product = s.scalar(select(Product).where(Product.id == pid))
            assert product is not None
            product.description = product.description + " Now with a redesigned handle."
            new_doc = build_product_document(product)
            s.commit()
        with Session(engine) as s:
            refresh_product_embedding(s, pid)
            s.commit()
        with Session(engine) as s:
            after = _product_vector(s, pid)
            row = s.scalar(
                select(Embedding).where(
                    Embedding.source_type == "product", Embedding.source_id == pid
                )
            )
            assert row is not None
            assert row.chunk_text == new_doc, "stored doc must match the rebuilt document"

        assert len(after) == embed_dim
        assert after != before, "changed source text must change the embedding"
    finally:
        engine.dispose()
