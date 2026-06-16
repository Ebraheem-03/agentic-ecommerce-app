"""SQLAlchemy 2.0 typed ORM models for the Hearth data layer (US-E3-04).

These models map 1:1 onto the schema authored by the Alembic migrations
(``api/alembic/versions/0001..0003``), which are the SOURCE OF TRUTH. The models
do NOT define the schema — they mirror it so the app gets typed, mapped access and
so ``app.db.seed`` can write rows through the ORM. Parity is proven by
``tests/db/test_models_parity.py`` (no metadata diff vs the migrated DB).

Design notes:
- All models register on the single shared ``app.db.base.Base`` (Alembic's
  ``target_metadata``), so a future autogenerate sees them.
- Native Postgres ENUM types are referenced BY NAME with ``create_type=False`` so
  SQLAlchemy never tries to re-create the types migration 0001 already made.
- Server defaults (``uuid_generate_v7()``, ``now()``, booleans, ``'{}'::jsonb``)
  are mirrored so the ORM doesn't fight the DB and so inserts can omit them.
- ``embeddings.embedding`` is a pgvector ``Vector`` sized from ``settings.embed_dim``
  — never a hardcoded dimension (Echo owns the final value).

Importing this package registers every table on ``Base.metadata``.
"""

from __future__ import annotations

from app.db.models.agent import AgentAction, Conversation, Message
from app.db.models.cache import SemanticCacheEntry
from app.db.models.cart import Cart, CartItem
from app.db.models.catalog import (
    Inventory,
    Product,
    ProductImage,
    Review,
    Store,
    Variant,
)
from app.db.models.embedding import Embedding
from app.db.models.idempotency import IdempotencyKey
from app.db.models.order import Order, OrderItem, Payment
from app.db.models.policy import Policy
from app.db.models.returns import Return, ReturnItem
from app.db.models.user import Address, Session, User

__all__ = [
    "Address",
    "AgentAction",
    "Cart",
    "CartItem",
    "Conversation",
    "Embedding",
    "IdempotencyKey",
    "Inventory",
    "Message",
    "Order",
    "OrderItem",
    "Payment",
    "Policy",
    "Product",
    "ProductImage",
    "Return",
    "ReturnItem",
    "Review",
    "SemanticCacheEntry",
    "Session",
    "Store",
    "User",
    "Variant",
]
