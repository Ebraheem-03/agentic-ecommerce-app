"""API smoke suite (US-QA-D08) — the boot/docs/CORS surface gate.

This is *the API smoke*: it proves the app boots, mounts its full router inventory,
renders its docs, serves a valid OpenAPI document, and wires CORS correctly (allowed
and disallowed origins). It runs entirely over ASGI via ``TestClient`` with **no
database**, so it stays fast and deterministic in CI without the pgvector service.

Scope split (kept deliberately non-overlapping):
  * ``test_api_smoke`` (this file) — boot / app surface / docs / OpenAPI / CORS, plus
    one cross-group spot-check that the canonical error envelope is wired app-wide.
  * ``test_error_envelope`` — per-``ErrorCode`` mapping detail (501/404/422 bodies,
    allowed-origin preflight). The smoke suite does not re-assert that detail.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# One representative path per mounted router group. If the app boots and mounts its
# full inventory, every one of these must appear in the OpenAPI ``paths``. Note the
# catalog group is mounted at ``/products`` + ``/stores`` (no ``/catalog`` prefix).
ROUTER_GROUP_PATHS = [
    "/auth/login",  # auth
    "/products",  # catalog
    "/search",  # search
    "/cart",  # cart
    "/orders",  # orders
    "/returns",  # returns
    "/agent/conversations",  # agent
    "/seller/products",  # seller
    "/admin/policies",  # admin
]


# --- boot / app surface ----------------------------------------------------------


def test_app_imports_and_health_boots() -> None:
    """The app object imports and the liveness probe answers 200 ``{"status":"ok"}``."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.parametrize("path", ROUTER_GROUP_PATHS)
def test_full_router_inventory_is_mounted(path: str) -> None:
    """A representative path from every router group is present in the schema."""
    paths = app.openapi()["paths"]
    assert path in paths, f"router group path {path!r} is not mounted"


# --- docs render -----------------------------------------------------------------


def test_docs_renders_scalar_reference() -> None:
    """``/docs`` serves the Scalar HTML reference (house standard), not Swagger UI."""
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    body = resp.text
    assert "scalar" in body.lower()  # Scalar marker
    assert app.openapi_url is not None
    assert app.openapi_url in body  # references the OpenAPI document url


def test_openapi_json_is_a_valid_document() -> None:
    """``/openapi.json`` is a valid OpenAPI doc exposing the mounted route groups."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    doc: dict[str, Any] = resp.json()
    assert doc["openapi"].startswith("3.")
    assert isinstance(doc["paths"], dict) and doc["paths"]
    for path in ROUTER_GROUP_PATHS:
        assert path in doc["paths"]


# --- CORS surface ----------------------------------------------------------------


def test_cors_allowed_origin_echoed_on_actual_request() -> None:
    """A real ``GET /health`` from the allowed origin carries the ACAO header back."""
    resp = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_disallowed_origin_is_not_echoed() -> None:
    """A preflight from an unlisted origin must not get that origin echoed back."""
    resp = client.options(
        "/auth/login",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert resp.headers.get("access-control-allow-origin") != "http://evil.example"


# --- error envelope is wired app-wide (cross-group spot-check) --------------------


def test_envelope_is_app_wide_on_a_non_auth_group() -> None:
    """A stub from a *different* group than ``test_error_envelope`` (agent, not admin)
    still emits the canonical not_implemented envelope — proves it's app-wide, not
    bolted onto one router. (reviews/returns/seller are real now; GET /agent/_sse-events
    is a reference-only stub reachable without auth/body.)"""
    resp = client.get("/agent/_sse-events")
    assert resp.status_code == 501
    assert resp.json() == {
        "error": {
            "code": "not_implemented",
            "message": "We haven't built this one yet — it lands in Week 2.",
            "details": None,
        }
    }
