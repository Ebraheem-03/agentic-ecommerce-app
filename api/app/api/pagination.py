"""Opaque cursor pagination — one style for every list route (contract-v0 §3).

The contract locks **cursor-based** pagination: ``meta.next_cursor`` is an opaque
string the client echoes back to fetch the next page; ``limit`` is 1-100; ``total``
is best-effort. This module is the single, reusable implementation so every list
endpoint (catalog here, orders/search/returns later) paginates identically.

The cursor is a **keyset** cursor, not an offset: it encodes the sort key of the
last row on the page (``created_at`` + tiebreaker ``id``), base64url-wrapped so it's
opaque. Keyset beats OFFSET for stable, drift-free paging as rows are inserted.

Sort order across all list routes: ``created_at DESC, id DESC`` (newest first,
``id`` as a deterministic UUIDv7 tiebreaker). A page asks for ``limit + 1`` rows to
learn whether a next page exists without a second COUNT.
"""

from __future__ import annotations

import base64
import binascii
import json
from datetime import UTC, datetime
from typing import NamedTuple

from app.core.errors import APIError
from app.schemas.envelope import ErrorCode


class Cursor(NamedTuple):
    """The decoded keyset position: the ``(created_at, id)`` of the last seen row."""

    created_at: datetime
    id: str


def _invalid_cursor() -> APIError:
    return APIError(
        status_code=422,
        code=ErrorCode.validation_error,
        message="That page cursor wasn't valid.",
    )


def encode_cursor(created_at: datetime, row_id: str) -> str:
    """Pack a keyset position into an opaque base64url cursor string."""
    payload = json.dumps({"c": created_at.isoformat(), "i": row_id}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> Cursor:
    """Decode an opaque cursor back into a keyset position (422 on garbage)."""
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        obj = json.loads(raw)
        created_at = datetime.fromisoformat(obj["c"])
        row_id = obj["i"]
    except (binascii.Error, ValueError, KeyError, TypeError) as exc:
        raise _invalid_cursor() from exc
    if not isinstance(row_id, str):
        raise _invalid_cursor()
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return Cursor(created_at=created_at, id=row_id)
