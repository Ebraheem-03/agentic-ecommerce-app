"""Runtime error-envelope + CORS wiring tests (US-E4-01).

Asserts every non-2xx renders the canonical ``{"error": {code, message, details}}``
shape from contract-v0, and that a CORS preflight from an allowed origin is accepted.
These run against the app over ASGI (no DB needed) — they exercise the stub routes,
unknown paths, and validation failures, not business logic.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_stub_route_returns_not_implemented_envelope() -> None:
    # /auth/login and /products are real handlers now (US-E4-04 / US-E4-06); point at a
    # route that is STILL a contract stub so we keep asserting the canonical 501 envelope.
    # GET /products/{id}/reviews has no body/auth, so the 501 is reached without DB or
    # validation getting in the way (reviews land in a later story).
    resp = client.get("/products/anything/reviews")
    assert resp.status_code == 501
    assert resp.json() == {
        "error": {
            "code": "not_implemented",
            "message": "We haven't built this one yet — it lands in Week 2.",
            "details": None,
        }
    }


def test_unknown_path_returns_not_found_envelope() -> None:
    resp = client.get("/nope")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["details"] is None
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]


def test_invalid_body_returns_validation_error_envelope() -> None:
    # Missing required fields on the login body -> 422 with per-field details.
    resp = client.post("/auth/login", json={})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["details"], dict)
    assert body["error"]["details"]["errors"]  # non-empty per-field list


def test_cors_preflight_from_allowed_origin() -> None:
    resp = client.options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"
