"""API-facing string enums.

These MIRROR the native Postgres enum types declared in
``api/alembic/versions/0001_extension_and_enums.py`` (the source of truth) by VALUE.
They are duplicated here on purpose: API DTOs are a separate contract from the ORM,
and we want the OpenAPI/Scalar schema to enumerate the exact allowed values without
importing the data layer. If migration 0001 changes a value set, change it here too.

All members are ``str`` subclasses so they serialize as bare label strings.
"""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    buyer = "buyer"
    seller = "seller"
    support = "support"
    admin = "admin"


class StoreStatus(StrEnum):
    draft = "draft"
    active = "active"
    suspended = "suspended"


class ProductStatus(StrEnum):
    draft = "draft"
    active = "active"
    archived = "archived"


class StockState(StrEnum):
    """Product-level stock rollup for list / search / recommendation cards.

    Derived (not stored): the rollup over a product's active variants — a product
    is ``in_stock`` if its best-stocked variant is, ``out_of_stock`` only when none
    are sellable, ``low_stock`` for the thin band in between. Per-variant stock stays
    the boolean ``VariantOut.in_stock``; this is the card-level signal.
    """

    in_stock = "in_stock"
    low_stock = "low_stock"
    out_of_stock = "out_of_stock"


class CartStatus(StrEnum):
    open = "open"
    converted = "converted"
    abandoned = "abandoned"


class OrderStatus(StrEnum):
    placed = "placed"
    packed = "packed"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"


class FulfilStatus(StrEnum):
    pending = "pending"
    fulfilled = "fulfilled"
    cancelled = "cancelled"


class PaymentStatus(StrEnum):
    pending = "pending"
    authorized = "authorized"
    captured = "captured"
    failed = "failed"
    refunded = "refunded"


class ReturnStatus(StrEnum):
    requested = "requested"
    approved = "approved"
    rejected = "rejected"
    hitl_pending = "hitl_pending"
    refunded = "refunded"


class ReturnReason(StrEnum):
    damaged = "damaged"
    not_as_described = "not_as_described"
    wrong_item = "wrong_item"
    no_longer_needed = "no_longer_needed"
    arrived_late = "arrived_late"
    other = "other"


class PolicyKind(StrEnum):
    returns = "returns"
    shipping = "shipping"
    payments = "payments"
    care = "care"
    platform = "platform"


class ConversationSurface(StrEnum):
    buyer = "buyer"
    support = "support"
    seller = "seller"


class MessageRole(StrEnum):
    user = "user"
    assistant = "assistant"
    system = "system"
    tool = "tool"


class AgentOutcome(StrEnum):
    applied = "applied"
    refused = "refused"
    hitl_deferred = "hitl_deferred"
