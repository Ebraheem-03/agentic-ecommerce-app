"""Back-compat shim — the embedding seam now lives in ``app.services.embeddings``.

US-E4-08 formalized the ad-hoc seed stub into a pluggable provider (``Embedder``
protocol + ``StubEmbedder`` default, selected by ``settings.embed_provider``). The
seed no longer owns embedding logic; it goes through the service like every other
call site (e.g. future seller write handlers) so there is ONE provider seam.

This module re-exports the stub's public names so any existing import of
``app.db.seed.embeddings`` keeps working. Echo swaps providers in
``app.services.embeddings`` — never here. See ADR-0026.
"""

from __future__ import annotations

from app.services.embeddings import SEED_STUB_MODEL, StubEmbedder

__all__ = ["SEED_STUB_MODEL", "embed_text"]


def embed_text(text: str) -> list[float]:
    """Deterministic stub vector for ``text`` (delegates to the active stub embedder).

    Kept for back-compat. New code should use ``app.services.embeddings.get_embedder``.
    """
    return StubEmbedder().embed_text(text)
