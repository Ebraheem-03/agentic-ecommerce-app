"""Auth / identity request + response models.

Auth model (DRAFT, see contract-v0 [REVIEW]): opaque server-side **session token**
backed by the ``sessions`` table (``token_hash``, ``expires_at``), returned to the
client as a Bearer token. NOT a self-contained JWT — revocation is a row delete.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.enums import UserRole
from app.schemas.envelope import CamelModel


class RegisterRequest(CamelModel):
    """POST /auth/register — create a buyer (or seller) account."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(min_length=1, max_length=120)
    # Self-serve registration is buyer or seller; support/admin are provisioned.
    role: UserRole = UserRole.buyer


class LoginRequest(CamelModel):
    """POST /auth/login — exchange credentials for a session token."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserOut(CamelModel):
    """Public view of a user account (never exposes password_hash)."""

    id: str
    email: EmailStr
    display_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class SessionOut(CamelModel):
    """A freshly minted session — returned by register + login."""

    token: str = Field(description="Opaque bearer session token (send as Authorization).")
    expires_at: datetime
    user: UserOut


class LogoutResult(CamelModel):
    """Confirmation body for logout."""

    revoked: bool = True
