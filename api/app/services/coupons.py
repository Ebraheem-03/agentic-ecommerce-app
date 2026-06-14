"""Coupon validation — v0 deterministic stub (US-E5-01, ADR-0029).

There is NO coupons table yet. This service validates a coupon code against a small,
static in-process map and returns a typed discount. It exists so the agent's
``applyCoupon`` tool has a real, deterministic backing without coupling the tool layer
to a schema that doesn't exist.

DELIBERATE V0 SHIM (gap documented in ADR-0029):
  * codes live in ``_CODES`` (a module constant), not the database;
  * no per-user redemption tracking, no expiry, no min-spend, no stacking;
  * discounts are computed against a caller-supplied subtotal but NOT persisted.

A future epic replaces ``_CODES`` with a ``coupons`` table + redemption ledger; the
``validate_coupon`` signature (code [+ subtotal] -> ``CouponDiscount``) is the seam that
stays stable when that lands.

Discount kinds:
  * ``percent`` — N% off the subtotal (rounded down to whole minor units);
  * ``fixed``   — a flat minor-unit amount off (never more than the subtotal).
Unknown code -> ``APIError(404, not_found)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.core.errors import APIError
from app.schemas.envelope import ErrorCode


class CouponKind(StrEnum):
    """How a coupon's value is applied to a subtotal."""

    percent = "percent"
    fixed = "fixed"


@dataclass(frozen=True, slots=True)
class _CouponSpec:
    """A static coupon definition (v0 — no DB row behind it)."""

    kind: CouponKind
    value: int  # percent points (0..100) for percent; minor units for fixed


# Static v0 code map. Replaced by a coupons table in a future epic (ADR-0029).
_CODES: dict[str, _CouponSpec] = {
    "WELCOME10": _CouponSpec(kind=CouponKind.percent, value=10),
    "HEARTH5": _CouponSpec(kind=CouponKind.fixed, value=500),  # $5.00
}


@dataclass(frozen=True, slots=True)
class CouponDiscount:
    """The resolved discount for a valid coupon against a given subtotal."""

    code: str
    kind: CouponKind
    # The percent points (percent kind) or flat minor units (fixed kind) the coupon is
    # worth, BEFORE clamping to the subtotal.
    value: int
    # The actual minor-unit discount to apply to ``subtotal_minor`` (clamped: never
    # below 0, never above the subtotal).
    discount_minor: int
    currency: str


def _not_found() -> APIError:
    return APIError(
        status_code=404,
        code=ErrorCode.not_found,
        message="We couldn't find that coupon code.",
    )


def _normalize(code: str) -> str:
    """Coupon codes are matched case-insensitively, trimmed of surrounding space."""
    return code.strip().upper()


def validate_coupon(
    code: str, *, subtotal_minor: int, currency: str = "USD"
) -> CouponDiscount:
    """Validate ``code`` and compute its discount against ``subtotal_minor``.

    Returns a typed ``CouponDiscount`` for a known code; raises ``APIError(404,
    not_found)`` for an unknown one. The discount is clamped to ``[0, subtotal_minor]``
    so it can never exceed the order value or go negative.
    """
    spec = _CODES.get(_normalize(code))
    if spec is None:
        raise _not_found()

    if spec.kind is CouponKind.percent:
        raw = (subtotal_minor * spec.value) // 100
    else:
        raw = spec.value

    discount = max(0, min(raw, subtotal_minor))
    return CouponDiscount(
        code=_normalize(code),
        kind=spec.kind,
        value=spec.value,
        discount_minor=discount,
        currency=currency,
    )
