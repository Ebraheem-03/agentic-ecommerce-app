"""Unit/contract tests for the auth handlers (US-E4-04 / US-E4-05, ADR-0023).

DB-backed: each test runs the real FastAPI app (``api_client``) against a freshly
migrated + seeded throwaway Postgres (``seeded_db``). These assert the *handler*
behavior (status + envelope + side effects); Juno owns the broader E2E journeys.

Skips cleanly when no Postgres is reachable (the ``migration_db`` chain calls
``pytest.skip``), so the DB-free suite stays runnable everywhere.
"""

from __future__ import annotations

from typing import Any

from tests.conftest import ContractClient, SeededDb
from tests.fixtures.handles import PERSONAS, TEST_PASSWORD

NEW_EMAIL = "newcomer@buyers.hearth.test"
NEW_PASSWORD = "a-strong-enough-pw"


def _register(client: ContractClient, email: str, password: str) -> Any:
    return client.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": "New Comer"},
    )


# --- register --------------------------------------------------------------------


def test_register_creates_unverified_account_with_session(
    api_client: ContractClient, seeded_db: SeededDb
) -> None:
    """Register returns 201 + a session token; the new account is unverified."""
    resp = _register(api_client, NEW_EMAIL, NEW_PASSWORD)
    assert resp.status_code == 201
    body = resp.json()
    assert body["meta"] is None
    data = body["data"]
    assert data["token"] and isinstance(data["token"], str)
    assert data["user"]["email"] == NEW_EMAIL
    assert data["user"]["role"] == "buyer"
    # No password hash ever leaks in the public view.
    assert "password_hash" not in data["user"]


def test_register_duplicate_live_email_conflicts(
    api_client: ContractClient, seeded_db: SeededDb
) -> None:
    """A second register on a seeded live email is a 409 ``email_taken``."""
    resp = _register(api_client, PERSONAS["buyer_primary"].email, NEW_PASSWORD)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "email_taken"


# --- login -----------------------------------------------------------------------


def test_login_seeded_persona_succeeds(
    api_client: ContractClient, seeded_db: SeededDb
) -> None:
    """A seeded (verified) persona logs in: 200 + session token."""
    persona = PERSONAS["buyer_primary"]
    resp = api_client.post(
        "/auth/login", json={"email": persona.email, "password": TEST_PASSWORD}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["token"]


def test_login_bad_password_is_401(
    api_client: ContractClient, seeded_db: SeededDb
) -> None:
    """Wrong password -> 401 unauthenticated (does not reveal the email exists)."""
    persona = PERSONAS["buyer_primary"]
    resp = api_client.post(
        "/auth/login", json={"email": persona.email, "password": "wrong-password"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


def test_login_unknown_email_is_401(
    api_client: ContractClient, seeded_db: SeededDb
) -> None:
    """Unknown email -> 401 unauthenticated (same code as bad password)."""
    resp = api_client.post(
        "/auth/login", json={"email": "nobody@buyers.hearth.test", "password": "x" * 10}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


def test_login_unverified_email_is_403(
    api_client: ContractClient, seeded_db: SeededDb
) -> None:
    """A freshly-registered (unverified) account is blocked from login with 403."""
    _register(api_client, NEW_EMAIL, NEW_PASSWORD)
    # A registered-but-unverified client logs in via a *fresh* client (no token).
    resp = api_client.post(
        "/auth/login", json={"email": NEW_EMAIL, "password": NEW_PASSWORD}
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


# --- me / logout / verify --------------------------------------------------------


def test_me_returns_current_user(
    api_client: ContractClient, seeded_db: SeededDb
) -> None:
    """``/auth/me`` returns the user behind the bearer token."""
    persona = PERSONAS["seller_ceramics"]
    api_client.login(persona)
    resp = api_client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == persona.email


def test_me_without_token_is_401(
    api_client: ContractClient, seeded_db: SeededDb
) -> None:
    """``/auth/me`` with no Authorization header -> 401 unauthenticated."""
    resp = api_client.get("/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


def test_logout_revokes_session(
    api_client: ContractClient, seeded_db: SeededDb
) -> None:
    """Logout deletes the session row; the token no longer authenticates."""
    api_client.login(PERSONAS["buyer_primary"])
    resp = api_client.post("/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["data"]["revoked"] is True
    # The same (now-revoked) token must fail on a protected route.
    after = api_client.get("/auth/me")
    assert after.status_code == 401


def test_verify_flips_email_verified_and_unblocks_login(
    api_client: ContractClient, seeded_db: SeededDb
) -> None:
    """Register (unverified) -> verify -> the account can now log in (200)."""
    reg = _register(api_client, NEW_EMAIL, NEW_PASSWORD)
    # api_client now holds the new account's session token (from register).
    api_client.token = reg.json()["data"]["token"]
    verified = api_client.post("/auth/verify")
    assert verified.status_code == 200

    fresh = ContractClient(api_client._raw)  # no token
    resp = fresh.post("/auth/login", json={"email": NEW_EMAIL, "password": NEW_PASSWORD})
    assert resp.status_code == 200
    assert resp.json()["data"]["token"]
