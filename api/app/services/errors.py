"""Shared domain-error constructors for the service layer (US-E4-10).

Every state-mutating service raises ``APIError`` (never a bare ``HTTPException``) so the
canonical envelope + a closed ``ErrorCode`` are guaranteed. These small constructors
centralize the messages/codes the orders + cart surfaces share so they stay consistent.
"""

from __future__ import annotations

from app.core.errors import APIError
from app.schemas.envelope import ErrorCode


def not_found(thing: str) -> APIError:
    return APIError(
        status_code=404,
        code=ErrorCode.not_found,
        message=f"We couldn't find that {thing}.",
    )


def out_of_stock(available: int) -> APIError:
    return APIError(
        status_code=409,
        code=ErrorCode.out_of_stock,
        message="That's more than we have in stock right now.",
        details={"available": available},
    )


def empty_cart_error() -> APIError:
    return APIError(
        status_code=409,
        code=ErrorCode.empty_cart,
        message="Your cart is empty — add something before checking out.",
    )


def payment_declined() -> APIError:
    return APIError(
        status_code=402,
        code=ErrorCode.payment_declined,
        message="That payment was declined. Your order is still open — try again.",
    )
