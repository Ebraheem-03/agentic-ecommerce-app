"""Auth end-to-end journey + scope-denial suite (US-QA-D09, ADR-0023).

LAYER SPLIT (mirrors the Day-8 smoke vs envelope split):

* ``app/.../test_auth_handlers.py`` (Orion) is the **unit** layer — it pins each
  handler's behavior in isolation (hashing, the dummy-verify timing path, the exact
  APIError each branch raises). It does not stitch the steps into a journey.
* THIS module is the **integration / journey** layer. It drives the real ASGI app
  against a real migrated+seeded throwaway Postgres (the ``seeded_db`` + ``api_client``
  fixtures) and walks the full lifecycle a client actually experiences —
  register -> verify -> login -> protected route -> logout -> denied — plus every
  negative branch end to end. We assert on the closed ``ErrorCode`` (and HTTP status),
  never on prose, so the contract — not wording — is what's locked.

Determinism: every test gets a pristine migrated+seeded DB (per-test CREATE/DROP via
``migration_db`` -> ``seeded_db``), unique registration emails use ``.test`` (RFC 6761,
allowed through ``EmailStr`` per ADR-0024), and expiry is forced by writing the session
row's ``expires_at`` into the past rather than sleeping.

Scope (US-E4-05): no business route is role-guarded yet (the routers are still 501
stubs), so we exercise ``require_role`` as a *real route dependency* on a tiny test-only
app that reuses the production auth dependency, error handlers, and the same throwaway
DB. That asserts the genuine 403 ``forbidden`` wiring without waiting on a real scoped
endpoint to land.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import Depends, FastAPI
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.api.deps import require_role
from app.api.routers import auth as auth_router
from app.core.errors import install_error_handlers
from app.db.models import User
from app.db.models.user import Session as SessionRow
from app.schemas.auth import UserOut
from app.schemas.envelope import Envelope
from tests.conftest import ContractClient, SeededDb
from tests.fixtures.handles import PERSONAS

# A persona the seed marks verified, so its credentials log in straight away.
VERIFIED_PERSONA = PERSONAS["buyer_primary"]
ADMIN_PERSONA = PERSONAS["admin"]

# Unique, EmailStr-valid (.test TLD) addresses for fresh registrations.
NEW_EMAIL = "newcomer@buyers.hearth.test"
GOOD_PASSWORD = "CHANGE_ME_good_pw"


# --------------------------------------------------------------------------- #
# Scope-denial fixture: a real route guarded by the production require_role.    #
# --------------------------------------------------------------------------- #
@pytest.fixture
def scoped_client(seeded_db: SeededDb) -> Iterator[ContractClient]:
    """A client over a tiny app that mounts the real auth router + one admin-only route.

    The route depends on the production ``require_role("admin")`` and the app installs
    the production error handlers, so a wrong-role caller gets the genuine canonical
    ``403 forbidden`` envelope. ``get_session`` resolves the DB URL at request time, so
    this app hits the same migrated+seeded throwaway DB as ``seeded_db``.
    """
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(auth_router.router)

    @app.get("/admin-only", response_model=Envelope[UserOut])
    def admin_only(
        user: User = Depends(require_role("admin")),  # noqa: B008
    ) -> Envelope[UserOut]:
        return Envelope(data=UserOut.model_validate(user))

    with TestClient(app, base_url="http://testserver") as raw:
        yield ContractClient(raw)


def _expire_session(seeded_db: SeededDb, token: str) -> None:
    """Force the live session behind ``token`` to be expired (deterministic, no sleep)."""
    from app.core.security import hash_token

    with Session(seeded_db.engine) as s:
        s.execute(
            update(SessionRow)
            .where(SessionRow.token_hash == hash_token(token))
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        s.commit()


# --------------------------------------------------------------------------- #
# Happy path — the full lifecycle, end to end.                                 #
# --------------------------------------------------------------------------- #
def test_full_lifecycle_register_verify_login_me_logout_denied(
    api_client: ContractClient, seeded_db: SeededDb
) -> None:
    """register -> (login blocked unverified) -> verify -> login -> /me -> logout -> denied."""
    # 1. Register: 201, returns a session envelope; account starts unverified.
    reg = api_client.post(
        "/auth/register",
        json={
            "email": NEW_EMAIL,
            "password": GOOD_PASSWORD,
            "display_name": "Newcomer",
            "role": "buyer",
        },
    )
    assert reg.status_code == 201
    body = reg.json()
    assert body["meta"] is None
    data = body["data"]
    reg_token = data["token"]
    assert isinstance(reg_token, str) and reg_token
    assert data["user"]["email"] == NEW_EMAIL
    assert data["user"]["role"] == "buyer"

    # 2. Login is denied while unverified -> 403 forbidden.
    denied = api_client.post(
        "/auth/login", json={"email": NEW_EMAIL, "password": GOOD_PASSWORD}
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "forbidden"

    # 3. Verify using the registration session token (auth-required stub).
    api_client.token = reg_token
    verified = api_client.post("/auth/verify")
    assert verified.status_code == 200
    assert verified.json()["data"]["email"] == NEW_EMAIL

    # 4. Login now succeeds -> 200 with a fresh token.
    login = api_client.post(
        "/auth/login", json={"email": NEW_EMAIL, "password": GOOD_PASSWORD}
    )
    assert login.status_code == 200
    login_token = login.json()["data"]["token"]
    assert isinstance(login_token, str) and login_token

    # 5. Protected route /auth/me with the login token returns the current user.
    api_client.token = login_token
    me = api_client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["email"] == NEW_EMAIL

    # 6. Logout revokes the session row.
    out = api_client.post("/auth/logout")
    assert out.status_code == 200
    assert out.json()["data"]["revoked"] is True

    # 7. The revoked token is now rejected on a protected route -> 401.
    again = api_client.get("/auth/me")
    assert again.status_code == 401
    assert again.json()["error"]["code"] == "unauthenticated"


def test_seeded_persona_login_then_me(
    api_client: ContractClient, seeded_db: SeededDb
) -> None:
    """A seeded (already-verified) persona can log in and read /auth/me."""
    api_client.login(VERIFIED_PERSONA)
    me = api_client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["email"] == VERIFIED_PERSONA.email


# --------------------------------------------------------------------------- #
# Negative paths.                                                              #
# --------------------------------------------------------------------------- #
def test_login_bad_password_is_401(
    api_client: ContractClient, seeded_db: SeededDb
) -> None:
    """Right email, wrong password -> 401 unauthenticated (not 403/404)."""
    resp = api_client.post(
        "/auth/login",
        json={"email": VERIFIED_PERSONA.email, "password": "CHANGE_ME_wrong_pw"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


def test_login_unknown_email_is_401_indistinguishable(
    api_client: ContractClient, seeded_db: SeededDb
) -> None:
    """Unknown email -> 401 unauthenticated, identical to the bad-password code."""
    resp = api_client.post(
        "/auth/login",
        json={"email": "nobody@buyers.hearth.test", "password": GOOD_PASSWORD},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


def test_login_unverified_account_is_403(
    api_client: ContractClient, seeded_db: SeededDb
) -> None:
    """A freshly registered (unverified) account is blocked at login with 403 forbidden."""
    reg = api_client.post(
        "/auth/register",
        json={
            "email": "unverified@buyers.hearth.test",
            "password": GOOD_PASSWORD,
            "display_name": "Unverified",
            "role": "buyer",
        },
    )
    assert reg.status_code == 201
    resp = api_client.post(
        "/auth/login",
        json={"email": "unverified@buyers.hearth.test", "password": GOOD_PASSWORD},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_register_duplicate_email_is_409(
    api_client: ContractClient, seeded_db: SeededDb
) -> None:
    """Registering an email that already exists (a seeded persona) -> 409 email_taken."""
    resp = api_client.post(
        "/auth/register",
        json={
            "email": VERIFIED_PERSONA.email,
            "password": GOOD_PASSWORD,
            "display_name": "Imposter",
            "role": "buyer",
        },
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "email_taken"


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param(None, id="missing-header"),
        pytest.param({"Authorization": "Bearer not-a-real-token"}, id="garbage-token"),
        pytest.param({"Authorization": "Basic abc123"}, id="wrong-scheme"),
    ],
)
def test_protected_route_rejects_bad_auth_401(
    api_client: ContractClient,
    seeded_db: SeededDb,
    headers: dict[str, str] | None,
) -> None:
    """Missing / garbage / wrong-scheme Authorization on /auth/me -> 401 unauthenticated."""
    resp = api_client.get("/auth/me", headers=headers)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


def test_protected_route_rejects_expired_token_401(
    api_client: ContractClient, seeded_db: SeededDb
) -> None:
    """An expired session token is rejected on a protected route -> 401 unauthenticated."""
    token = api_client.login(VERIFIED_PERSONA)
    _expire_session(seeded_db, token)
    resp = api_client.get("/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"
    # NOTE: ADR-0023 calls the expired-row delete a "may be lazily deleted" — it is
    # best-effort. Here the request transaction rolls back when the 401 propagates, so we
    # deliberately do NOT assert the row is gone: the contract is the 401, not the reap.


def test_sliding_window_bumps_expiry_on_use(
    api_client: ContractClient, seeded_db: SeededDb
) -> None:
    """Each authenticated request pushes ``expires_at`` forward (sliding 7-day, ADR-0023)."""
    from app.core.security import hash_token

    token = api_client.login(VERIFIED_PERSONA)

    def _expiry() -> datetime:
        with Session(seeded_db.engine) as s:
            row = s.scalar(
                select(SessionRow).where(SessionRow.token_hash == hash_token(token))
            )
            assert row is not None
            return row.expires_at

    # Pull the recorded expiry back so a subsequent authed call must move it forward.
    past = datetime.now(UTC) + timedelta(days=1)
    with Session(seeded_db.engine) as s:
        s.execute(
            update(SessionRow)
            .where(SessionRow.token_hash == hash_token(token))
            .values(expires_at=past)
        )
        s.commit()

    me = api_client.get("/auth/me")
    assert me.status_code == 200
    assert _expiry() > past  # the request renewed the window


# --------------------------------------------------------------------------- #
# Scope (US-E4-05): wrong-role on a role-guarded route -> 403 forbidden.        #
# --------------------------------------------------------------------------- #
def test_scoped_route_denies_wrong_role_403(
    scoped_client: ContractClient,
) -> None:
    """A buyer hitting an admin-only route gets 403 forbidden via require_role."""
    scoped_client.login(VERIFIED_PERSONA)  # buyer
    resp = scoped_client.get("/admin-only")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_scoped_route_allows_right_role(
    scoped_client: ContractClient,
) -> None:
    """The admin persona is allowed through the same require_role-guarded route -> 200."""
    scoped_client.login(ADMIN_PERSONA)
    resp = scoped_client.get("/admin-only")
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "admin"


def test_scoped_route_unauthenticated_is_401(
    scoped_client: ContractClient,
) -> None:
    """No token on the role-guarded route fails auth first -> 401 unauthenticated."""
    resp = scoped_client.get("/admin-only")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"
