"""Replay-safe idempotency for money-touching routes (US-E4-10, ADR-0028).

Backed by the ``idempotency_keys`` table (migration 0006). A stored row memos a prior
successful request keyed by ``(user_id, key, endpoint)``; a replay re-emits the saved
status + body verbatim instead of re-running the handler (contract-v0 §1.3).

``key`` is the client's ``Idempotency-Key`` header (or the body fallback). When no key
is supplied, ``lookup`` returns ``None`` and ``store`` is a no-op — the route still runs,
it just isn't replay-protected (the one-open-cart -> converted transition is the
secondary guard against double-checkout).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IdempotencyKey


@dataclass(frozen=True, slots=True)
class StoredResult:
    """A previously-stored response: the HTTP status + the serialized JSON body."""

    status_code: int
    body: dict[str, Any]


def lookup(
    session: Session, user_id: str, key: str | None, endpoint: str
) -> StoredResult | None:
    """Return the stored result for ``(user, key, endpoint)`` or ``None`` (no key/miss)."""
    if not key:
        return None
    row = session.scalars(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.key == key,
            IdempotencyKey.endpoint == endpoint,
        )
    ).first()
    if row is None:
        return None
    return StoredResult(status_code=row.status_code, body=row.response_json)


def _to_json(body: BaseModel | dict[str, Any]) -> dict[str, Any]:
    if isinstance(body, BaseModel):
        return body.model_dump(mode="json")
    return body


def store(
    session: Session,
    user_id: str,
    key: str | None,
    endpoint: str,
    *,
    status_code: int,
    body: BaseModel | dict[str, Any],
) -> None:
    """Persist the result so a later replay of ``(user, key, endpoint)`` re-emits it.

    No-op when no key was supplied. Caller flushes/commits via the session lifecycle.
    """
    if not key:
        return
    session.add(
        IdempotencyKey(
            user_id=user_id,
            key=key,
            endpoint=endpoint,
            status_code=status_code,
            response_json=_to_json(body),
        )
    )
    session.flush()
