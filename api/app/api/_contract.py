"""Shared helpers for the CONTRACT-DRAFT routers (US-E4-00).

Every route handler in this layer is a deliberate stub: it raises ``not_implemented``
so the OpenAPI/Scalar page renders the full contract (paths, models, responses) for
human review WITHOUT any business logic existing yet. Swap ``stub()`` for real logic
per-endpoint in the Week-2 build stories.

``ERROR_RESPONSES`` is attached to every route so Scalar documents the canonical
error envelope on each operation.
"""

from __future__ import annotations

from typing import Any, NoReturn

from fastapi import HTTPException, status

from app.schemas.envelope import ErrorResponse

# Reusable OpenAPI ``responses`` block: documents the single error envelope.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    "4XX": {"model": ErrorResponse, "description": "Canonical error envelope."},
    "5XX": {"model": ErrorResponse, "description": "Canonical error envelope."},
}


def stub() -> NoReturn:
    """Contract placeholder — no implementation yet (US-E4-00)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="not_implemented: contract draft (US-E4-00); handler lands in Week-2.",
    )
