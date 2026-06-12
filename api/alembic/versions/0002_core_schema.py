"""core schema — all tables, constraints, indexes (excl. embeddings)

Revision ID: 0002_core_schema
Revises: 0001_ext_enums
Create Date: 2026-06-12

Authors the full relational schema from docs/data/erd.md (human-APPROVED
2026-06-12), minus the pgvector `embeddings` table (its own dimension-driven
migration, 0003). Hand-written SQL so we control UUIDv7 defaults, partial-unique
indexes, CHECK constraints and native-enum references precisely.

UUIDv7 strategy: base Postgres 16 has no native uuidv7(), so we install a small
`uuid_generate_v7()` SQL function built on core `gen_random_uuid()` (pgcrypto) —
time-ordered ids, no extra extension. It's the server-side column default; the app
may also supply its own v7 ids (the default just covers seeds/manual inserts).
See docs/decisions/0018-uuidv7-and-pgvector-dim.md.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_core_schema"
down_revision: str | None = "0001_ext_enums"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UUIDV7_FN = """
CREATE OR REPLACE FUNCTION uuid_generate_v7()
RETURNS uuid
LANGUAGE plpgsql
VOLATILE
AS $$
DECLARE
    unix_ts_ms bytea;
    uuid_bytes bytea;
BEGIN
    -- 48-bit big-endian Unix timestamp in milliseconds.
    unix_ts_ms = substring(int8send((extract(epoch FROM clock_timestamp()) * 1000)::bigint) from 3);
    -- Start from a random v4 uuid (pgcrypto is in PG16 core) and overlay the parts.
    uuid_bytes = uuid_send(gen_random_uuid());
    -- Bytes 0..5 = timestamp.
    uuid_bytes = overlay(uuid_bytes placing unix_ts_ms from 1 for 6);
    -- Byte 6: set version to 7 (0111) in the high nibble, keep low nibble random.
    uuid_bytes = set_byte(uuid_bytes, 6, (b'0111' || get_byte(uuid_bytes, 6)::bit(4))::bit(8)::int);
    -- Byte 8: set variant to RFC 4122 (10xxxxxx).
    uuid_bytes = set_byte(uuid_bytes, 8, (b'10' || get_byte(uuid_bytes, 8)::bit(6))::bit(8)::int);
    RETURN encode(uuid_bytes, 'hex')::uuid;
END;
$$;
"""


SCHEMA = r"""
-- ========================== users / auth ==============================
CREATE TABLE users (
    id            uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
    email         text NOT NULL,
    password_hash text,
    display_name  text NOT NULL,
    role          user_role NOT NULL DEFAULT 'buyer',
    is_active     boolean NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    deleted_at    timestamptz
);
-- Unique email only among live (non-soft-deleted) accounts.
CREATE UNIQUE INDEX uq_users_email_live ON users (email) WHERE deleted_at IS NULL;

CREATE TABLE sessions (
    id         uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
    user_id    uuid REFERENCES users (id) ON DELETE CASCADE,
    token_hash text NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_sessions_user_id ON sessions (user_id);

CREATE TABLE addresses (
    id             uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
    user_id        uuid REFERENCES users (id) ON DELETE CASCADE,
    recipient_name text NOT NULL,
    line1          text NOT NULL,
    line2          text,
    city           text NOT NULL,
    region         text NOT NULL,
    postal_code    text NOT NULL,
    country_code   text NOT NULL,
    is_default     boolean NOT NULL DEFAULT false,
    created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_addresses_user_id ON addresses (user_id);

-- ========================== stores / catalog ==========================
CREATE TABLE stores (
    id         uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
    owner_id   uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name       text NOT NULL,
    slug       text NOT NULL UNIQUE,
    location   text,
    bio        text,
    status     store_status NOT NULL DEFAULT 'draft',
    payout_pct integer NOT NULL DEFAULT 88,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_stores_owner_id ON stores (owner_id);

CREATE TABLE products (
    id           uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
    store_id     uuid NOT NULL REFERENCES stores (id) ON DELETE CASCADE,
    title        text NOT NULL,
    slug         text NOT NULL UNIQUE,
    description  text NOT NULL DEFAULT '',
    category     text,
    attributes   jsonb NOT NULL DEFAULT '{}'::jsonb,
    status       product_status NOT NULL DEFAULT 'draft',
    -- rating_avg / rating_count are DERIVED rollups of the reviews table
    -- (app-side recompute on review write for v0). Kept on the row so list
    -- cards don't aggregate per render.
    rating_avg   numeric(2,1),
    rating_count integer NOT NULL DEFAULT 0,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    deleted_at   timestamptz
);
CREATE INDEX ix_products_store_id ON products (store_id);

CREATE TABLE reviews (
    id         uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
    product_id uuid NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    user_id    uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    rating     smallint NOT NULL,
    title      text,
    body       text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_reviews_rating_range CHECK (rating BETWEEN 1 AND 5),
    -- One review per (product, user).
    CONSTRAINT uq_reviews_product_id_user_id UNIQUE (product_id, user_id)
);
CREATE INDEX ix_reviews_product_id ON reviews (product_id);

CREATE TABLE variants (
    id          uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
    product_id  uuid NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    sku         text NOT NULL UNIQUE,
    options     jsonb NOT NULL DEFAULT '{}'::jsonb,
    price_minor bigint NOT NULL,
    currency    text NOT NULL DEFAULT 'USD',
    is_active   boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_variants_price_nonneg CHECK (price_minor >= 0)
);
CREATE INDEX ix_variants_product_id ON variants (product_id);

CREATE TABLE product_images (
    id         uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
    product_id uuid NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    variant_id uuid REFERENCES variants (id) ON DELETE SET NULL,
    url        text NOT NULL,
    alt        text NOT NULL DEFAULT '',
    position   integer NOT NULL DEFAULT 0
);
CREATE INDEX ix_product_images_product_id ON product_images (product_id);

CREATE TABLE inventory (
    id               uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
    variant_id       uuid NOT NULL UNIQUE REFERENCES variants (id) ON DELETE CASCADE,
    qty_on_hand      integer NOT NULL DEFAULT 0,
    qty_reserved     integer NOT NULL DEFAULT 0,
    restock_eta_days integer,
    updated_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_inventory_qty_nonneg CHECK (qty_on_hand >= 0 AND qty_reserved >= 0)
);

-- ========================== carts =====================================
CREATE TABLE carts (
    id         uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
    user_id    uuid REFERENCES users (id) ON DELETE CASCADE,
    anon_token text,
    status     cart_status NOT NULL DEFAULT 'open',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
-- At most one OPEN cart per user.
CREATE UNIQUE INDEX uq_carts_one_open_per_user
    ON carts (user_id) WHERE status = 'open' AND user_id IS NOT NULL;

CREATE TABLE cart_items (
    id         uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
    cart_id    uuid NOT NULL REFERENCES carts (id) ON DELETE CASCADE,
    variant_id uuid NOT NULL REFERENCES variants (id) ON DELETE CASCADE,
    qty        integer NOT NULL DEFAULT 1,
    added_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_cart_items_qty_pos CHECK (qty > 0),
    CONSTRAINT uq_cart_items_cart_id_variant_id UNIQUE (cart_id, variant_id)
);

-- ========================== orders ====================================
CREATE TABLE orders (
    id             uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
    order_number   text NOT NULL UNIQUE,
    user_id        uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    cart_id        uuid REFERENCES carts (id) ON DELETE SET NULL,
    status         order_status NOT NULL DEFAULT 'placed',
    subtotal_minor bigint NOT NULL DEFAULT 0,
    shipping_minor bigint NOT NULL DEFAULT 0,
    tax_minor      bigint NOT NULL DEFAULT 0,
    total_minor    bigint NOT NULL DEFAULT 0,
    currency       text NOT NULL DEFAULT 'USD',
    ship_address   jsonb,
    placed_at      timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_orders_user_id ON orders (user_id);

CREATE TABLE order_items (
    id                  uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
    order_id            uuid NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    variant_id          uuid REFERENCES variants (id) ON DELETE SET NULL,
    title_snapshot      text NOT NULL,
    options_snapshot    jsonb NOT NULL DEFAULT '{}'::jsonb,
    store_name_snapshot text NOT NULL,
    unit_price_minor    bigint NOT NULL,
    qty                 integer NOT NULL,
    fulfil_status       fulfil_status NOT NULL DEFAULT 'pending',
    CONSTRAINT ck_order_items_qty_pos CHECK (qty > 0)
);
CREATE INDEX ix_order_items_order_id ON order_items (order_id);

CREATE TABLE payments (
    id           uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
    order_id     uuid NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    status       payment_status NOT NULL DEFAULT 'pending',
    provider_ref text,
    amount_minor bigint NOT NULL,
    currency     text NOT NULL DEFAULT 'USD',
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_payments_order_id ON payments (order_id);

-- ========================== returns ===================================
CREATE TABLE returns (
    id            uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
    order_id      uuid NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    status        return_status NOT NULL DEFAULT 'requested',
    reason_code   return_reason NOT NULL,
    note          text,
    within_window boolean NOT NULL DEFAULT true,
    approved_by   uuid REFERENCES users (id) ON DELETE SET NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    resolved_at   timestamptz
);
CREATE INDEX ix_returns_order_id ON returns (order_id);

CREATE TABLE return_items (
    id            uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
    return_id     uuid NOT NULL REFERENCES returns (id) ON DELETE CASCADE,
    order_item_id uuid NOT NULL REFERENCES order_items (id) ON DELETE CASCADE,
    qty           integer NOT NULL,
    CONSTRAINT ck_return_items_qty_pos CHECK (qty > 0)
);
CREATE INDEX ix_return_items_return_id ON return_items (return_id);

-- ========================== policies (RAG source) =====================
CREATE TABLE policies (
    id             uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
    store_id       uuid REFERENCES stores (id) ON DELETE CASCADE,
    kind           policy_kind NOT NULL,
    title          text NOT NULL,
    body           text NOT NULL,
    is_active      boolean NOT NULL DEFAULT true,
    version        integer NOT NULL DEFAULT 1,
    effective_from timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_policies_store_id ON policies (store_id);

-- ========================== agent persistence =========================
CREATE TABLE conversations (
    id                 uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
    user_id            uuid REFERENCES users (id) ON DELETE SET NULL,
    surface            conversation_surface NOT NULL DEFAULT 'buyer',
    context_order_id   uuid REFERENCES orders (id) ON DELETE SET NULL,
    context_product_id uuid REFERENCES products (id) ON DELETE SET NULL,
    created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_conversations_user_id ON conversations (user_id);

CREATE TABLE messages (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
    conversation_id uuid NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    role            message_role NOT NULL,
    content         text NOT NULL DEFAULT '',
    citations       jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_messages_conversation_id ON messages (conversation_id);

CREATE TABLE agent_actions (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
    conversation_id uuid REFERENCES conversations (id) ON DELETE SET NULL,
    actor_user_id   uuid REFERENCES users (id) ON DELETE SET NULL,
    action_type     text NOT NULL,
    payload         jsonb NOT NULL DEFAULT '{}'::jsonb,
    outcome         agent_outcome NOT NULL DEFAULT 'applied',
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_agent_actions_conversation_id ON agent_actions (conversation_id);
"""


# Drop order is the reverse of creation (children before parents).
DROP_TABLES = [
    "agent_actions",
    "messages",
    "conversations",
    "policies",
    "return_items",
    "returns",
    "payments",
    "order_items",
    "orders",
    "cart_items",
    "carts",
    "inventory",
    "product_images",
    "variants",
    "reviews",
    "products",
    "stores",
    "addresses",
    "sessions",
    "users",
]


def upgrade() -> None:
    op.execute(UUIDV7_FN)
    op.execute(SCHEMA)


def downgrade() -> None:
    for table in DROP_TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS uuid_generate_v7();")
