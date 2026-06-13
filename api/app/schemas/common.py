"""Small shared value objects used across resources."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.envelope import CamelModel


class Money(CamelModel):
    """A money amount in minor units (cents), with currency.

    Mirrors the ``*_minor`` BigInteger columns + ``currency`` Text in the ORM.
    """

    amount_minor: int = Field(ge=0, description="Amount in minor units (e.g. cents).")
    currency: str = Field(default="USD", min_length=3, max_length=3)


class AddressIn(CamelModel):
    """A shipping address payload (checkout + address book)."""

    recipient_name: str = Field(min_length=1, max_length=200)
    line1: str = Field(min_length=1, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=120)
    region: str = Field(min_length=1, max_length=120)
    postal_code: str = Field(min_length=1, max_length=32)
    country_code: str = Field(min_length=2, max_length=2)


class AddressOut(AddressIn):
    """A persisted address."""

    id: str
    is_default: bool = False
    created_at: datetime
