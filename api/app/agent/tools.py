"""Typed tool definitions + provider-agnostic registry (US-E5-01, ADR-0029).

The product's agents call the catalog/cart/orders domain through a fixed set of TOOLS.
Each tool is defined once here as:

  * a Pydantic v2 **input** model (``extra="forbid"`` so the LLM can't smuggle args),
  * a typed **output** (an existing DTO, or a small purpose-built model), and
  * a ``ToolSpec`` that exposes a provider-agnostic, serializable description for LLM
    function-calling: ``name`` + ``description`` + JSON schema of the params
    (``input_model.model_json_schema()``).

The registry (``REGISTRY`` / ``tool_specs()``) is the single source of truth the
executor (``app.agent.executor``) and, later, the agent loop read from. NO provider
(Groq/Gemini) specifics live here — ``tool_specs()`` returns plain dicts a caller maps
onto whatever the chosen provider's function-calling shape is.

The 8 tools:

  read  : search, productDetails, inventory, orderStatus
  mutate: addToCart, draftOrder (idempotent), refund (sensitive)
  pure  : applyCoupon (deterministic; v0 coupon shim — ADR-0029)

This module is DEFINITIONS only — scope/idempotency/retry/audit live in the executor.
Juno owns the comprehensive per-tool E2E matrix (US-QA-D12); Echo's tests here prove
schema generation + example parsing + the spec is serializable.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.catalog import ProductSummary
from app.schemas.order import OrderDetail, PaymentIntentOut, PaymentOut
from app.schemas.search import SearchMode


class ToolName(StrEnum):
    """Closed set of tool names. Doubles as the ``action_type`` written to audit."""

    search = "search"
    product_details = "productDetails"
    inventory = "inventory"
    add_to_cart = "addToCart"
    apply_coupon = "applyCoupon"
    draft_order = "draftOrder"
    order_status = "orderStatus"
    refund = "refund"


# --------------------------------------------------------------------------- #
# Tool I/O base — strict inputs; outputs reuse existing DTOs where possible.   #
# --------------------------------------------------------------------------- #
class _ToolInput(BaseModel):
    """Base for every tool's input: forbid unknown keys so LLM args stay in-contract."""

    model_config = ConfigDict(extra="forbid")


class _ToolOutput(BaseModel):
    """Base for purpose-built tool outputs (DTO reuse is preferred where it fits)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)


# --------------------------------------------------------------------------- #
# 1. search                                                                    #
# --------------------------------------------------------------------------- #
class SearchInput(_ToolInput):
    """Query the catalog for products matching free-text ``query``."""

    query: str = Field(min_length=1, max_length=400, description="Free-text search query.")
    category: str | None = Field(
        default=None, max_length=200, description="Optional category filter."
    )
    limit: int = Field(default=10, ge=1, le=50, description="Max results to return.")


class ScoredProductOut(_ToolOutput):
    """One search hit: a product summary plus its relevance score."""

    product: ProductSummary
    score: float | None = Field(
        default=None, description="Relevance score for the active retriever."
    )


class SearchOutput(_ToolOutput):
    """The ranked search page plus which retrieval mode served it."""

    results: list[ScoredProductOut]
    mode: SearchMode


# --------------------------------------------------------------------------- #
# 2. productDetails                                                            #
# --------------------------------------------------------------------------- #
class ProductDetailsInput(_ToolInput):
    """Fetch full detail for a product by id or slug."""

    id_or_slug: str = Field(
        min_length=1, max_length=200, description="Product UUID or slug."
    )


# productDetails output is the existing ``ProductDetail`` DTO directly.


# --------------------------------------------------------------------------- #
# 3. inventory                                                                 #
# --------------------------------------------------------------------------- #
class InventoryInput(_ToolInput):
    """Check stock/availability for a product (optionally a single variant)."""

    product_id_or_slug: str = Field(
        min_length=1, max_length=200, description="Product UUID or slug."
    )
    variant_id: str | None = Field(
        default=None,
        max_length=200,
        description="Optional: restrict the answer to one variant.",
    )


class VariantStockOut(_ToolOutput):
    """Per-variant stock signal (no exact counts — keeps stock levels private)."""

    variant_id: str
    sku: str
    in_stock: bool
    restock_eta_days: int | None = None


class InventoryOutput(_ToolOutput):
    """Availability for a product: overall flag + per-variant signal."""

    product_id: str
    any_in_stock: bool
    variants: list[VariantStockOut]


# --------------------------------------------------------------------------- #
# 4. addToCart (mutating)                                                      #
# --------------------------------------------------------------------------- #
class AddToCartInput(_ToolInput):
    """Add (or increment) a variant in the acting buyer's open cart."""

    variant_id: str = Field(min_length=1, max_length=200, description="Variant UUID.")
    qty: int = Field(default=1, ge=1, le=999, description="Quantity to add.")


# addToCart output is the existing ``CartOut`` DTO directly.


# --------------------------------------------------------------------------- #
# 5. applyCoupon (pure / deterministic)                                        #
# --------------------------------------------------------------------------- #
class ApplyCouponInput(_ToolInput):
    """Validate a coupon code and compute its discount against a subtotal."""

    code: str = Field(min_length=1, max_length=64, description="Coupon code.")
    subtotal_minor: int = Field(
        ge=0, description="Subtotal (minor units) to apply the discount against."
    )
    currency: str = Field(default="USD", min_length=3, max_length=3)


class CouponDiscountOut(_ToolOutput):
    """The resolved discount for a valid coupon (v0 shim — ADR-0029)."""

    code: str
    kind: str
    value: int = Field(description="Percent points (percent) or minor units (fixed).")
    discount_minor: int = Field(ge=0, description="Discount to apply, clamped to subtotal.")
    currency: str


# --------------------------------------------------------------------------- #
# 6. draftOrder (mutating, idempotent)                                         #
# --------------------------------------------------------------------------- #
class DraftOrderInput(_ToolInput):
    """Prepare an order for the user to confirm: checkout the open cart + create a
    payment intent, WITHOUT confirming payment."""

    ship_address: dict[str, object] = Field(
        description="Shipping address for the order (recipient_name, line1, city, ...)."
    )


class DraftOrderOutput(_ToolOutput):
    """A placed (unpaid) order plus its mock payment intent, ready for confirmation."""

    order: OrderDetail
    payment_intent: PaymentIntentOut


# --------------------------------------------------------------------------- #
# 7. orderStatus (read)                                                        #
# --------------------------------------------------------------------------- #
class OrderStatusInput(_ToolInput):
    """Look up an order's status + detail timeline by id."""

    order_id: str = Field(min_length=1, max_length=200, description="Order UUID.")


# orderStatus output is the existing ``OrderDetail`` DTO directly.


# --------------------------------------------------------------------------- #
# 8. refund (mutating, sensitive)                                             #
# --------------------------------------------------------------------------- #
class RefundInput(_ToolInput):
    """Refund the captured payment on an order (v0: mark Payment -> refunded)."""

    order_id: str = Field(min_length=1, max_length=200, description="Order UUID.")
    reason: str | None = Field(
        default=None, max_length=400, description="Optional reason for the refund."
    )


class RefundOutput(_ToolOutput):
    """The refunded payment (v0 thin shim — full returns/refund epic is later)."""

    order_id: str
    payment: PaymentOut


# --------------------------------------------------------------------------- #
# Registry — the provider-agnostic spec the executor + agent loop read from.    #
# --------------------------------------------------------------------------- #
class ToolSpec(BaseModel):
    """A single tool's static definition. ``model_json_schema()`` on ``input_model``
    yields the params schema; ``provider_schema()`` packages it for function-calling.

    Flags drive the executor (not the LLM): ``mutating`` gates idempotency + retry
    policy; ``sensitive`` requires the owner/support/admin scope; ``read_only`` is the
    any-authed-user scope class.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    name: ToolName
    description: str
    input_model: type[BaseModel]
    mutating: bool = False
    sensitive: bool = False

    @property
    def read_only(self) -> bool:
        return not self.mutating

    def params_schema(self) -> dict[str, Any]:
        """JSON schema for the tool's params (the input model's schema)."""
        return self.input_model.model_json_schema()

    def provider_schema(self) -> dict[str, Any]:
        """Provider-agnostic function-calling descriptor (name/description/parameters).

        A serializable dict; the agent loop maps it onto the chosen provider's tool
        shape (e.g. ``{"type": "function", "function": {...}}``) without this layer
        knowing which provider that is.
        """
        return {
            "name": self.name.value,
            "description": self.description,
            "parameters": self.params_schema(),
        }


REGISTRY: dict[ToolName, ToolSpec] = {
    ToolName.search: ToolSpec(
        name=ToolName.search,
        description=(
            "Search the product catalog with a free-text query; returns ranked product "
            "summaries with relevance scores. Use to discover products."
        ),
        input_model=SearchInput,
    ),
    ToolName.product_details: ToolSpec(
        name=ToolName.product_details,
        description=(
            "Fetch full detail for one product (variants, prices, images, stock, rating) "
            "by its id or slug."
        ),
        input_model=ProductDetailsInput,
    ),
    ToolName.inventory: ToolSpec(
        name=ToolName.inventory,
        description=(
            "Check stock availability for a product (and optionally a single variant). "
            "Returns in-stock flags and any restock ETA — never exact counts."
        ),
        input_model=InventoryInput,
    ),
    ToolName.add_to_cart: ToolSpec(
        name=ToolName.add_to_cart,
        description="Add or increment a product variant in the shopper's open cart.",
        input_model=AddToCartInput,
        mutating=True,
    ),
    ToolName.apply_coupon: ToolSpec(
        name=ToolName.apply_coupon,
        description=(
            "Validate a coupon code and compute the discount it would apply to a "
            "subtotal. Does not persist anything."
        ),
        input_model=ApplyCouponInput,
    ),
    ToolName.draft_order: ToolSpec(
        name=ToolName.draft_order,
        description=(
            "Prepare an order for the shopper to confirm: check out the open cart "
            "(placing the order) and create a payment intent, WITHOUT taking payment."
        ),
        input_model=DraftOrderInput,
        mutating=True,
    ),
    ToolName.order_status: ToolSpec(
        name=ToolName.order_status,
        description="Get an order's current status, items, and payment timeline by id.",
        input_model=OrderStatusInput,
    ),
    ToolName.refund: ToolSpec(
        name=ToolName.refund,
        description=(
            "Refund the captured payment on an order. Sensitive: only the order owner "
            "or a support/admin user may invoke it."
        ),
        input_model=RefundInput,
        mutating=True,
        sensitive=True,
    ),
}


def tool_specs() -> list[dict[str, Any]]:
    """All tools as provider-agnostic, JSON-serializable function-calling descriptors."""
    return [spec.provider_schema() for spec in REGISTRY.values()]


__all__ = [
    "REGISTRY",
    "AddToCartInput",
    "ApplyCouponInput",
    "CouponDiscountOut",
    "DraftOrderInput",
    "DraftOrderOutput",
    "InventoryInput",
    "InventoryOutput",
    "OrderStatusInput",
    "ProductDetailsInput",
    "RefundInput",
    "RefundOutput",
    "ScoredProductOut",
    "SearchInput",
    "SearchOutput",
    "ToolName",
    "ToolSpec",
    "VariantStockOut",
    "tool_specs",
]
