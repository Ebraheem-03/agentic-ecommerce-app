"""Idempotency keys — replay-safe checkout + payment (US-E4-10).

Mirrors migration ``0006_idempotency_keys`` (the source of truth). A stored row is the
memo of a prior successful, money-touching request: replaying the same
``(user_id, key, endpoint)`` re-emits ``response_json`` with ``status_code`` rather than
re-running the handler (contract-v0 §1.3). See ADR-0028.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._shared import created_at_col, uuid_pk


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(Text, nullable=False)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        UniqueConstraint(
            "user_id", "key", "endpoint", name="uq_idempotency_user_key_endpoint"
        ),
        Index("ix_idempotency_keys_user_id", "user_id"),
    )
