"""Deterministic stand-in embedding generation for the seed (US-E3-03).

ECHO COORDINATION POINT
=======================
``embed_text`` is the SINGLE function Echo replaces with a real provider call
(Groq/Gemini). Until then it returns a deterministic, hash-derived vector so the
seed is reproducible and re-runnable. Two hard contracts the replacement MUST keep:

1. Output length == ``settings.embed_dim`` (the pgvector column dimension). NEVER
   hardcode 768 — read it from settings so a dim change (one down/up on migration
   0003) doesn't break the seed.
2. ``model`` is a clearly-placeholder label (``SEED_STUB_MODEL``) so stub rows are
   trivially distinguishable from real ones and can be re-embedded in bulk.

The stub is NOT semantically meaningful (cosine distance between two stub vectors is
meaningless) — it exists only to satisfy NOT NULL + the dimension contract so the
retrieval plumbing can be wired and tested before real embeddings land.
"""

from __future__ import annotations

import hashlib
import struct

from app.core.config import settings

# Placeholder model tag written into embeddings.model for every seeded row. Echo's
# real implementation should write the actual model id instead.
SEED_STUB_MODEL = "seed-stub"


def embed_text(text: str) -> list[float]:
    """Return a deterministic ``settings.embed_dim``-length vector for ``text``.

    REPLACE THIS BODY (only the body) with a real embedding call. Keep the
    signature and the length contract. Implementation: stream bytes from a SHA-256
    keyed on the text, unpack to floats in [-1, 1], cycle until the configured
    dimension is filled. Same text -> same vector (idempotent seeds).
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
