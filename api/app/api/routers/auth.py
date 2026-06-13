"""Auth routes (contract draft). Session-token model — see contract-v0 [REVIEW]."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api._contract import ERROR_RESPONSES, stub
from app.schemas.auth import (
    LoginRequest,
    LogoutResult,
    RegisterRequest,
    SessionOut,
    UserOut,
)
from app.schemas.envelope import Envelope

router = APIRouter(prefix="/auth", tags=["auth"], responses=ERROR_RESPONSES)


@router.post(
    "/register",
    response_model=Envelope[SessionOut],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
)
def register(body: RegisterRequest) -> Envelope[SessionOut]:
    """Create a buyer/seller account and return a session token. (J-SEL-01)"""
    stub()


@router.post(
    "/login",
    response_model=Envelope[SessionOut],
    summary="Log in (exchange credentials for a session token)",
)
def login(body: LoginRequest) -> Envelope[SessionOut]:
    """Authenticate and mint a session token."""
    stub()


@router.post(
    "/logout",
    response_model=Envelope[LogoutResult],
    summary="Log out (revoke current session)",
)
def logout() -> Envelope[LogoutResult]:
    """Revoke the bearer session token (deletes the sessions row)."""
    stub()


@router.get(
    "/me",
    response_model=Envelope[UserOut],
    summary="Current authenticated user",
)
def me() -> Envelope[UserOut]:
    """Return the user behind the current session token."""
    stub()
