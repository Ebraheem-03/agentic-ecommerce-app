"""Top-level QA fixtures — the executable spine of the 'one source' plan (US-QA-D06).

These fixtures sit above the whole ``tests/`` tree so any layer's test module can
request them. They layer on Sable's throwaway-DB machinery (``tests/db/conftest.py``)
rather than re-implementing CREATE/DROP DATABASE:

    migration_db  (Sable)            -> fresh empty DB, Alembic Config + DSN
      └─ seeded_db (here)            -> migrate to head + run the idempotent seed
           ├─ handles                -> canonical handles resolved to REAL seed rows
           ├─ api_client             -> httpx client bound to the FastAPI app (ASGI)
           └─ persona_client(...)    -> api_client + a session token for a persona

The API client speaks the LOCKED contract-v0 (envelope ``{data, meta}``,
``Authorization: Bearer <token>``, closed error codes). Today every route is a 501
stub, so ``persona_client`` cannot really log a persona in: it is marked ``xfail``
with a clear reason until the Week-2 ``/auth/login`` handler lands. The POINT of
this story is the fixture wiring + shape, not green endpoint behavior.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session

import app.core.config as app_config
from alembic import command
from app.db.seed.run import seed

# Re-export Sable's throwaway-DB fixture so it's visible tree-wide (pytest resolves
# fixtures by name from any conftest on the path; importing makes the dependency
# explicit and lets `seeded_db` below depend on it directly).
from tests.db.conftest import migration_db, open_conn  # noqa: F401
from tests.fixtures.handles import (
    PERSONAS,
    POLICY_HANDLES,
    PRODUCT_HANDLES,
    VARIANT_HANDLES,
    Persona,
)


def _sqla_url(dsn: str) -> str:
    """libpq DSN (from migration_db) -> SQLAlchemy + psycopg URL."""
    return make_url(dsn).set(drivername="postgresql+psycopg").render_as_string(
        hide_password=False
    )


@dataclass(frozen=True, slots=True)
class SeededDb:
    """A migrated + seeded throwaway database, plus a SQLAlchemy engine on it.

    ``engine`` is for tests that introspect seeded rows directly (the anti-drift
    handle checks). ``dsn`` is the raw libpq string for psycopg if needed.
    """

    engine: Engine
    dsn: str


@pytest.fixture
def seeded_db(migration_db: tuple[Config, str]) -> Iterator[SeededDb]:  # noqa: F811
    """Migrate a fresh DB to head, run the idempotent seed, yield an engine on it.

    Built on Sable's ``migration_db`` (per-test CREATE/DROP DATABASE) so nothing
    leaks and every test gets a pristine baseline. The seed is idempotent, so this
    is the stable baseline all journeys build deltas on top of.
    """
    cfg, dsn = migration_db
    command.upgrade(cfg, "head")
    importlib.reload(app_config)

    engine = create_engine(_sqla_url(dsn), future=True)
    try:
        with Session(engine) as s:
            seed(s)
            s.commit()
        yield SeededDb(engine=engine, dsn=dsn)
    finally:
        engine.dispose()


# --------------------------------------------------------------------------- #
# Canonical handles, resolved against the live seeded DB (anti-drift).         #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class ResolvedHandles:
    """The canonical catalog with every handle proven to map to a real seeded row.

    ``user_ids`` / ``product_ids`` / ``variant_ids`` / ``policy_ids`` map a handle's
    natural key to the DB-assigned UUID, so a test can go straight from
    ``handles.user_ids['buyer_primary']`` to a row without re-querying.
    """

    user_ids: dict[str, str]
    product_ids: dict[str, str]
    variant_ids: dict[str, str]
    policy_ids: dict[str, str]


@pytest.fixture
def handles(seeded_db: SeededDb) -> ResolvedHandles:
    """Resolve every canonical handle to its seeded UUID; fail loudly if any is stale.

    This is the per-layer anti-drift guarantee in fixture form: if the seed drops or
    renames a handle's natural key, resolution raises here and every dependent test
    fails fast (same spirit as the golden-eval resolver).
    """
    from sqlalchemy import select

    from app.db.models import Policy, Product, Store, User, Variant

    with Session(seeded_db.engine) as s:
        user_ids: dict[str, str] = {}
        for p in PERSONAS.values():
            uid = s.scalar(select(User.id).where(User.email == p.email, User.deleted_at.is_(None)))
            assert uid is not None, f"persona {p.handle!r} email {p.email!r} not seeded"
            user_ids[p.handle] = str(uid)

        product_ids: dict[str, str] = {}
        for ph in PRODUCT_HANDLES.values():
            pid = s.scalar(select(Product.id).where(Product.slug == ph.slug))
            assert pid is not None, f"product {ph.handle!r} slug {ph.slug!r} not seeded"
            product_ids[ph.handle] = str(pid)

        variant_ids: dict[str, str] = {}
        for vh in VARIANT_HANDLES.values():
            vid = s.scalar(select(Variant.id).where(Variant.sku == vh.sku))
            assert vid is not None, f"variant {vh.handle!r} sku {vh.sku!r} not seeded"
            variant_ids[vh.handle] = str(vid)

        policy_ids: dict[str, str] = {}
        for poh in POLICY_HANDLES.values():
            store_id = None
            if poh.store_slug is not None:
                store_id = s.scalar(select(Store.id).where(Store.slug == poh.store_slug))
                assert store_id is not None, f"policy {poh.handle!r} store missing"
            stmt = select(Policy.id).where(Policy.kind == poh.kind, Policy.title == poh.title)
            stmt = (
                stmt.where(Policy.store_id == store_id)
                if store_id is not None
                else stmt.where(Policy.store_id.is_(None))
            )
            pid = s.scalar(stmt)
            assert pid is not None, f"policy {poh.handle!r} ({poh.key}) not seeded"
            policy_ids[poh.handle] = str(pid)

    return ResolvedHandles(
        user_ids=user_ids,
        product_ids=product_ids,
        variant_ids=variant_ids,
        policy_ids=policy_ids,
    )


# --------------------------------------------------------------------------- #
# API client — speaks contract-v0 against the FastAPI app over ASGI.           #
# --------------------------------------------------------------------------- #
class LoginNotReady(RuntimeError):
    """Raised when /auth/login is still a contract stub (drives xfail)."""


class ContractClient:
    """Wraps an ``httpx.Client`` with contract-v0 ergonomics (Bearer auth + login).

    Speaks the LOCKED contract: ``{data, meta}`` envelope, ``Authorization: Bearer``,
    closed error codes. ``login`` POSTs ``/auth/login`` and stashes the session token.
    """

    def __init__(self, raw: httpx.Client) -> None:
        self._raw = raw
        self.token: str | None = None

    def _headers(self, extra: dict[str, str] | None) -> dict[str, str]:
        h: dict[str, str] = {}
        if self.token is not None:
            h["Authorization"] = f"Bearer {self.token}"
        if extra:
            h.update(extra)
        return h

    def request(
        self, method: str, url: str, *, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> httpx.Response:
        return self._raw.request(method, url, headers=self._headers(headers), **kwargs)

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def login(self, persona: Persona) -> str:
        """POST /auth/login per contract-v0, stash + return the Bearer token.

        Contract: 200 with ``{"data": SessionOut{token, expires_at, user}, "meta": null}``.
        Raises ``LoginNotReady`` if the response isn't the success envelope (e.g. while
        the handler is a 501 stub) — callers wrap this in xfail until Week-2.
        """
        resp = self.post(
            "/auth/login", json={"email": persona.email, "password": persona.password}
        )
        if resp.status_code != 200:
            raise LoginNotReady(
                f"/auth/login returned {resp.status_code} (expected 200). "
                "Auth handler is a contract stub until Week-2."
            )
        token = resp.json()["data"]["token"]
        assert isinstance(token, str) and token
        self.token = token
        return token


@pytest.fixture
def api_client() -> Iterator[ContractClient]:
    """An httpx client bound to the FastAPI app via ASGI (no network, no server).

    Uses Starlette's ``TestClient`` (an ``httpx.Client`` subclass that drives the ASGI
    app synchronously via an event-loop portal), wrapped in a ``ContractClient`` for
    the envelope + Bearer-auth conventions of contract-v0. Works the moment the real
    handlers land; until then callers that need a real session use ``persona_client``
    (xfail-guarded).
    """
    from starlette.testclient import TestClient

    from app.main import app

    with TestClient(app, base_url="http://testserver") as raw:
        yield ContractClient(raw)


@pytest.fixture
def persona_client(
    api_client: ContractClient, request: pytest.FixtureRequest
) -> ContractClient:
    """Parametrizable: an ``api_client`` already logged in as the requested persona.

    Use via ``@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)``.
    Until the auth handler lands, login raises ``LoginNotReady``; mark such tests
    ``xfail(raises=LoginNotReady)``.
    """
    persona_handle = getattr(request, "param", "buyer_primary")
    persona = PERSONAS[persona_handle]
    api_client.login(persona)
    return api_client
