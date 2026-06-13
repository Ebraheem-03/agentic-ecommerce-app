"""Shared column/type helpers for the ORM models.

Centralizes the recurring data-layer conventions (UUIDv7 server default, timestamptz
``now()`` defaults, native-enum references) so every model expresses them identically
and so a convention change is a one-file edit. See docs/decisions/0018 and the ORM
package docstring.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

# Server-side UUIDv7 default — the in-DB plpgsql fn installed by migration 0002.
UUIDV7_DEFAULT = text("uuid_generate_v7()")
# Server-side current timestamp default.
NOW_DEFAULT = text("now()")


# Native PG ENUM types and their ordered labels — MUST match migration 0001
# (api/alembic/versions/0001_extension_and_enums.py), the source of truth. Kept
# here so the ORM can validate enum strings on write without re-creating the types.
ENUM_LABELS: dict[str, tuple[str, ...]] = {
    "user_role": ("buyer", "seller", "support", "admin"),
    "store_status": ("draft", "active", "suspended"),
    "product_status": ("draft", "active", "archived"),
    "cart_status": ("open", "converted", "abandoned"),
    "order_status": ("placed", "packed", "shipped", "delivered", "cancelled"),
    "fulfil_status": ("pending", "fulfilled", "cancelled"),
    "payment_status": ("pending", "authorized", "captured", "failed", "refunded"),
    "return_status": ("requested", "approved", "rejected", "hitl_pending", "refunded"),
    "return_reason": (
        "damaged",
        "not_as_described",
        "wrong_item",
        "no_longer_needed",
        "arrived_late",
        "other",
    ),
    "policy_kind": ("returns", "shipping", "payments", "care", "platform"),
    "conversation_surface": ("buyer", "support", "seller"),
    "message_role": ("user", "assistant", "system", "tool"),
    "agent_outcome": ("applied", "refused", "hitl_deferred"),
    "embedding_source": ("product", "policy"),
}


def pg_enum(type_name: str) -> Enum:
    """Reference an EXISTING native Postgres ENUM type by name.

    ``create_type=False`` is critical: the enum types are created once in migration
    0001; SQLAlchemy must reference them, never attempt to CREATE TYPE them again.
    The labels (from ``ENUM_LABELS``, mirroring 0001) are passed so the ORM can
    validate strings on write — but columns are still typed as plain ``str`` (we map
    no Python Enum class), so callers use the bare label values.
    """
    labels = ENUM_LABELS[type_name]
    return Enum(
        *labels,
        name=type_name,
        native_enum=True,
        create_type=False,
        validate_strings=True,
    )


def uuid_pk() -> Mapped[str]:
    """Primary-key column: uuid, server default ``uuid_generate_v7()``."""
    return mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=UUIDV7_DEFAULT,
    )


def created_at_col() -> Mapped[datetime]:
    """``created_at timestamptz NOT NULL DEFAULT now()``."""
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=NOW_DEFAULT,
    )


def updated_at_col() -> Mapped[datetime]:
    """``updated_at timestamptz NOT NULL DEFAULT now()``."""
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=NOW_DEFAULT,
    )
