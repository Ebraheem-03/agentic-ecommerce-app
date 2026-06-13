"""Response envelope, pagination, and the canonical error shape.

CONTRACT DRAFT (US-E4-00) — these are the reusable wrappers every endpoint returns.

Success envelope: ``{"data": <resource | list>, "meta": <Meta | null>}``.
  - Single-resource reads/writes return ``data`` = the resource, ``meta`` = null.
  - List reads return ``data`` = list, ``meta`` = ``PageMeta`` (cursor pagination).

Error envelope: ``{"error": {"code": <ErrorCode>, "message": str, "details": ...}}``.
  - ``code`` is a CLOSED, documented set (``ErrorCode``) so QA assertions are
    deterministic. ``details`` is optional structured context (e.g. field errors).

IDs are UUIDv7 strings; timestamps are timezone-aware ISO-8601 (``datetime``).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class CamelModel(BaseModel):
    """Base model: strict, forbids unknown request fields, populates by field name.

    Response field names stay snake_case (matches the ORM + keeps Python idiomatic);
    the frontend contract is snake_case across the board for v0.
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)


# --------------------------------------------------------------------------- #
# Pagination — cursor-based (opaque cursor), one style across every list route. #
# --------------------------------------------------------------------------- #
class PageMeta(BaseModel):
    """List metadata for cursor pagination."""

    model_config = ConfigDict(extra="forbid")

    next_cursor: str | None = Field(
        default=None,
        description="Opaque cursor for the next page; null when no more results.",
    )
    limit: int = Field(description="Page size that was applied.", ge=1, le=100)
    total: int | None = Field(
        default=None,
        description="Total matching rows when cheaply known; null otherwise.",
    )


class Envelope[DataT](BaseModel):
    """Success envelope for a single resource (``meta`` is null)."""

    model_config = ConfigDict(extra="forbid")

    data: DataT
    meta: None = None


class ListEnvelope[DataT](BaseModel):
    """Success envelope for a list of resources with pagination ``meta``."""

    model_config = ConfigDict(extra="forbid")

    data: list[DataT]
    meta: PageMeta


# --------------------------------------------------------------------------- #
# Error shape — ONE canonical body, closed code set.                          #
# --------------------------------------------------------------------------- #
class ErrorCode(StrEnum):
    """Closed set of machine-readable error codes. HTTP status in parens.

    Keep this in lockstep with ``docs/api/contract-v0.md`` §Error catalog.
    """

    # 400 / 422
    validation_error = "validation_error"  # 422 — request failed schema/business rules
    # 401 / 403
    unauthenticated = "unauthenticated"  # 401 — missing/invalid session token
    forbidden = "forbidden"  # 403 — authed but wrong role/owner
    # 404
    not_found = "not_found"  # 404 — resource id does not exist / not visible
    # 409 — state conflicts
    conflict = "conflict"  # 409 — generic state conflict
    cart_already_open = "cart_already_open"  # 409 — one-open-cart-per-user violated
    duplicate_review = "duplicate_review"  # 409 — one review per (product,user)
    email_taken = "email_taken"  # 409 — email already registered (live)
    out_of_stock = "out_of_stock"  # 409 — insufficient inventory at add/checkout
    return_window_closed = "return_window_closed"  # 409 — outside return window
    empty_cart = "empty_cart"  # 409 — checkout with no items
    # 402 — test-mode payment
    payment_declined = "payment_declined"  # 402 — mock payment intent declined
    # 429 / 500
    rate_limited = "rate_limited"  # 429 — too many requests
    internal_error = "internal_error"  # 500 — unexpected server fault
    not_implemented = "not_implemented"  # 501 — contract stub, no logic yet


class ErrorBody(BaseModel):
    """Inner error object."""

    model_config = ConfigDict(extra="forbid")

    code: ErrorCode
    message: str = Field(description="Human-readable, plain-spoken (brand tone).")
    details: dict[str, object] | None = Field(
        default=None,
        description="Optional structured context, e.g. per-field validation errors.",
    )


class ErrorResponse(BaseModel):
    """Canonical error envelope returned for every non-2xx response."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorBody
