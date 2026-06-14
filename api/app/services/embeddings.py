"""Pluggable embedding provider seam + refresh-on-change service (US-E4-08).

THE ECHO SWAP SEAM
==================
The live embedding model is still an open human ``[DECISION]`` (Week-4, tied to the
free-tier Groq/Gemini key — see ADR-0026). Nothing here hardcodes a real provider.
Instead we expose a tiny pluggable seam:

* ``Embedder`` — the Protocol every provider satisfies: ``embed_text(text) -> vector``
  and ``embed_batch(texts) -> list[vector]``, plus a ``model`` tag written into
  ``embeddings.model`` so rows are attributable / bulk-re-embeddable.
* ``StubEmbedder`` — the default. Deterministic, content-derived, ``model="seed-stub"``,
  length == ``settings.embed_dim`` (NEVER hardcoded). Same text -> same vector, so the
  seed stays idempotent and "embeddings refresh on update" is testable: changed text
  yields a changed vector.
* ``get_embedder()`` — resolves the active provider from ``settings.embed_provider``
  (default ``"stub"``). Echo registers a real provider (e.g. ``GeminiEmbedder``) in
  ``_PROVIDERS`` and flips ``EMBED_PROVIDER`` — a ONE-LINE swap. No call site changes.

THE REFRESH PATH
================
``refresh_product_embedding(session, product_id)`` rebuilds a product's embeddable
document from its current name/description/category/attributes/variant options and
UPSERTS the single ``embeddings`` row (``source_type='product'``, ``chunk_index=0``).
The seed uses this; future seller write handlers (still stubs today) call the same
function so embeddings stay fresh whenever product text/attributes change.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.models import Embedding, Product, Variant

# Placeholder model tag written into embeddings.model for stub rows. Echo's real
# provider writes its actual model id instead, so stub rows are trivially found
# (WHERE model = 'seed-stub') for bulk re-embedding when the real model lands.
SEED_STUB_MODEL = "seed-stub"

# Source-type label for product embeddings (mirrors the embedding_source enum).
PRODUCT_SOURCE = "product"


class Embedder(Protocol):
    """A pluggable embedding provider. Echo's real provider satisfies this shape.

    Two hard contracts every implementation MUST keep:
    1. Each returned vector has length == ``settings.embed_dim`` (the pgvector column
       dimension). Read it from settings; never hardcode 768.
    2. ``model`` is a stable, attributable tag written into ``embeddings.model``.
    """

    @property
    def model(self) -> str: ...

    def embed_text(self, text: str) -> list[float]: ...

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]: ...


class StubEmbedder:
    """Deterministic, content-derived stand-in embedder (the default provider).

    NOT semantically meaningful — cosine distance between two stub vectors is
    meaningless. It exists only to satisfy ``NOT NULL`` + the dimension contract so the
    retrieval plumbing can be wired and tested before a real model lands. The vector is
    a function of the input text alone: identical text -> identical vector (idempotent
    seeds), changed text -> changed vector (proves refresh-on-update).
    """

    model = SEED_STUB_MODEL

    def embed_text(self, text: str) -> list[float]:
        """Return a deterministic ``settings.embed_dim``-length vector for ``text``.

        Stream bytes from a SHA-256 keyed on the text, unpack to floats in [-1, 1],
        cycle a counter until the configured dimension is filled.
        """
        dim = settings.embed_dim
        out: list[float] = []
        counter = 0
        while len(out) < dim:
            digest = hashlib.sha256(f"{text}\x00{counter}".encode()).digest()
            # 32-byte digest -> 8 floats (4 bytes each), scaled to [-1, 1].
            for i in range(0, 32, 4):
                (raw,) = struct.unpack(">I", digest[i : i + 4])
                out.append((raw / 0xFFFFFFFF) * 2.0 - 1.0)
                if len(out) >= dim:
                    break
            counter += 1
        return out[:dim]

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]


# Provider registry — the swap point. Echo adds e.g.
#   from app.services.gemini_embedder import GeminiEmbedder
#   _PROVIDERS["gemini"] = GeminiEmbedder
# and sets EMBED_PROVIDER=gemini. The factory is keyed lazily so a real provider's
# (possibly network-/key-dependent) construction only happens when selected.
_PROVIDERS: dict[str, type[Embedder]] = {
    "stub": StubEmbedder,
}


def get_embedder() -> Embedder:
    """Resolve the active embedding provider from ``settings.embed_provider``.

    Defaults to the deterministic ``StubEmbedder``. Unknown providers fail loudly so a
    typo in ``EMBED_PROVIDER`` never silently degrades to the stub in production.
    """
    name = settings.embed_provider
    try:
        provider_cls = _PROVIDERS[name]
    except KeyError:
        raise ValueError(
            f"Unknown EMBED_PROVIDER {name!r}. Registered: {sorted(_PROVIDERS)}. "
            "Echo registers real providers in app/services/embeddings.py::_PROVIDERS."
        ) from None
    return provider_cls()


# --------------------------------------------------------------------- document build


def build_product_document(product: Product) -> str:
    """Compose the embeddable text document for a product from its current fields.

    This is the single definition of "what a product's searchable text is" — title,
    description, category, attributes, and each active variant's options. Used by both
    the seed and the refresh path so the stored vector always matches the live row.
    Keep it deterministic (stable ordering) so identical content -> identical document
    -> identical stub vector.
    """
    parts: list[str] = [product.title, product.description]
    if product.category:
        parts.append(f"Category: {product.category}")
    if product.attributes:
        # Sort keys for a stable, content-only document (dict order is not contractual).
        attrs = ", ".join(
            f"{k}: {product.attributes[k]}" for k in sorted(product.attributes)
        )
        if attrs:
            parts.append(f"Attributes: {attrs}")
    variant_descs: list[str] = []
    for variant in sorted(product.variants, key=lambda v: v.sku):
        if not variant.is_active:
            continue
        opts = (
            json.dumps(variant.options, sort_keys=True)
            if variant.options
            else "{}"
        )
        variant_descs.append(f"{variant.sku} {opts}")
    if variant_descs:
        parts.append("Variants: " + "; ".join(variant_descs))
    return "\n".join(p for p in parts if p)


# ------------------------------------------------------------------------- upsert / refresh


def upsert_embedding(
    session: Session,
    *,
    source_type: str,
    source_id: str,
    chunk_index: int,
    text: str,
    embedder: Embedder | None = None,
) -> Embedding:
    """Upsert one embedding row on ``(source_type, source_id, chunk_index)``.

    Recomputes the vector + ``chunk_text`` from ``text`` through the active provider, so
    a content change (or a provider/dim change) is picked up in place. Returns the row.
    """
    emb = embedder or get_embedder()
    existing = session.scalar(
        select(Embedding).where(
            Embedding.source_type == source_type,
            Embedding.source_id == source_id,
            Embedding.chunk_index == chunk_index,
        )
    )
    if existing is None:
        existing = Embedding(
            source_type=source_type,
            source_id=source_id,
            chunk_index=chunk_index,
        )
        session.add(existing)
    existing.chunk_text = text
    existing.embedding = emb.embed_text(text)
    existing.model = emb.model
    return existing


def refresh_product_embedding(
    session: Session,
    product_id: str,
    *,
    embedder: Embedder | None = None,
) -> Embedding:
    """(Re)build and upsert a product's embedding from its CURRENT persisted fields.

    The reusable refresh entry point: the seed calls it, and future seller write
    handlers (product create/update — still stubs today) call it after committing a
    product text/attribute change so the stored vector stays in sync. Eager-loads
    variants so the document build never lazy-loads.

    Raises ``ValueError`` if the product id does not resolve (caller bug / race).
    """
    product = session.scalar(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.variants).selectinload(Variant.inventory))
    )
    if product is None:
        raise ValueError(f"refresh_product_embedding: no product with id {product_id!r}")
    document = build_product_document(product)
    return upsert_embedding(
        session,
        source_type=PRODUCT_SOURCE,
        source_id=product.id,
        chunk_index=0,
        text=document,
        embedder=embedder,
    )
