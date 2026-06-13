"""Idempotent seed package for the Hearth marketplace (US-E3-03).

Run as ``python -m app.db.seed`` (the entrypoint wired into
``api/scripts/db_reset.sh``). See ``run.py`` for orchestration, ``data.py`` for the
content, and ``embeddings.py`` for the Echo-replaceable embedding stub.
"""

from __future__ import annotations

from app.db.seed.run import main, seed

__all__ = ["main", "seed"]
