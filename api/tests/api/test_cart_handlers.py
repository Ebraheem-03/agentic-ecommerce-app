"""Cart endpoints — DB-backed handler/contract behavior (US-E4-09).

Exercises the LIVE cart write surface against the seeded throwaway DB via the
``seeded_db`` + ``persona_client`` fixture spine (contract-v0 ``{data, meta}`` envelope,
closed error codes, ``Authorization: Bearer``). Now that ``/auth/login`` is live,
``persona_client`` logs a real seeded buyer in.

LAYER SPLIT: these are handler-level (status + envelope + DB side effects). Juno owns
the full checkout E2E (US-QA-D11) — these stay at the cart boundary and do NOT assert
inventory mutation (the cart never reserves stock; reservation is US-E4-10).

Covers: lazy-create GET, add->201, add-again increments (idempotent upsert), PATCH sets
qty, PATCH qty=0 -> 422, DELETE removes, out_of_stock on over-request, cross-user line
access denied (404), and unauthenticated -> 401.
"""

from __future__ import annotations

import pytest

from app.schemas.envelope import ErrorCode
from tests.conftest import ContractClient, ResolvedHandles, SeededDb
from tests.fixtures.handles import PERSONAS, VARIANT_HANDLES


# --------------------------------------------------------------------------- #
# GET /cart — lazy create                                                      #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_get_cart_lazily_creates_open_cart(
    seeded_db: SeededDb, persona_client: ContractClient
) -> None:
    """First GET creates and returns an empty open cart in the canonical envelope."""
    resp = persona_client.get("/cart")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"data", "meta"}
    assert body["meta"] is None
    cart = body["data"]
    assert cart["status"] == "open"
    assert cart["items"] == []
    assert cart["subtotal_minor"] == 0
    assert cart["item_count"] == 0


@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_get_cart_is_stable_across_calls(
    seeded_db: SeededDb, persona_client: ContractClient
) -> None:
    """Repeated GET returns the SAME open cart (one-open-cart-per-user, not a new one)."""
    first = persona_client.get("/cart").json()["data"]
    second = persona_client.get("/cart").json()["data"]
    assert first["id"] == second["id"]


# --------------------------------------------------------------------------- #
# POST /cart/items — add + idempotent upsert                                   #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_add_item_returns_201_with_line(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """Adding an in-stock variant returns 201 with a populated, priced line."""
    variant_id = handles.variant_ids["mug_in_stock"]
    resp = persona_client.post("/cart/items", json={"variant_id": variant_id, "qty": 2})
    assert resp.status_code == 201
    cart = resp.json()["data"]
    assert len(cart["items"]) == 1
    line = cart["items"][0]
    assert line["variant_id"] == variant_id
    assert line["qty"] == 2
    assert line["unit_price_minor"] > 0
    assert line["line_total_minor"] == line["unit_price_minor"] * 2
    assert line["in_stock"] is True
    assert cart["item_count"] == 2
    assert cart["subtotal_minor"] == line["line_total_minor"]


@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_add_same_variant_increments_qty(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """Adding the same variant again upserts (one line, summed qty) — idempotent on key."""
    variant_id = handles.variant_ids["mug_in_stock"]
    persona_client.post("/cart/items", json={"variant_id": variant_id, "qty": 2})
    resp = persona_client.post("/cart/items", json={"variant_id": variant_id, "qty": 3})
    assert resp.status_code == 201
    cart = resp.json()["data"]
    assert len(cart["items"]) == 1  # still ONE line, not two
    assert cart["items"][0]["qty"] == 5
    assert cart["item_count"] == 5


@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_add_unknown_variant_is_404(
    seeded_db: SeededDb, persona_client: ContractClient
) -> None:
    """Adding a non-existent variant id -> 404 not_found (canonical envelope)."""
    resp = persona_client.post(
        "/cart/items",
        json={"variant_id": "00000000-0000-0000-0000-000000000000", "qty": 1},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == ErrorCode.not_found.value


# --------------------------------------------------------------------------- #
# out_of_stock                                                                 #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_add_out_of_stock_variant_conflicts(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """Adding the seeded zero-stock variant -> 409 out_of_stock."""
    variant_id = handles.variant_ids["wallet_oos"]
    resp = persona_client.post("/cart/items", json={"variant_id": variant_id, "qty": 1})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == ErrorCode.out_of_stock.value


@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_add_over_available_conflicts(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """Requesting more than the low-stock variant has on hand -> 409 out_of_stock."""
    low = VARIANT_HANDLES["mug_low_stock"]
    variant_id = handles.variant_ids["mug_low_stock"]
    resp = persona_client.post(
        "/cart/items", json={"variant_id": variant_id, "qty": low.qty_on_hand + 1}
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == ErrorCode.out_of_stock.value


@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_increment_over_available_conflicts(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """A second add whose CUMULATIVE qty exceeds stock -> 409 (checks resulting qty).

    Add one unit (in stock), then add a large delta: the check is against the RESULTING
    line qty, not the per-request delta, so the second add conflicts even though the
    first succeeded. Robust to seeded reserved stock (available <= qty_on_hand).
    """
    variant_id = handles.variant_ids["mug_low_stock"]
    ok = persona_client.post("/cart/items", json={"variant_id": variant_id, "qty": 1})
    assert ok.status_code == 201
    over = persona_client.post("/cart/items", json={"variant_id": variant_id, "qty": 999})
    assert over.status_code == 409
    assert over.json()["error"]["code"] == ErrorCode.out_of_stock.value


# --------------------------------------------------------------------------- #
# PATCH /cart/items/{id}                                                       #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_patch_sets_absolute_qty(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """PATCH sets the line to an absolute qty (not an increment)."""
    variant_id = handles.variant_ids["mug_in_stock"]
    added = persona_client.post(
        "/cart/items", json={"variant_id": variant_id, "qty": 2}
    ).json()["data"]
    item_id = added["items"][0]["id"]

    resp = persona_client.request("PATCH", f"/cart/items/{item_id}", json={"qty": 4})
    assert resp.status_code == 200
    cart = resp.json()["data"]
    assert cart["items"][0]["qty"] == 4
    assert cart["item_count"] == 4


@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_patch_qty_zero_is_422(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """qty=0 fails Pydantic validation (ge=1) -> 422 validation_error (use DELETE)."""
    variant_id = handles.variant_ids["mug_in_stock"]
    added = persona_client.post(
        "/cart/items", json={"variant_id": variant_id, "qty": 1}
    ).json()["data"]
    item_id = added["items"][0]["id"]

    resp = persona_client.request("PATCH", f"/cart/items/{item_id}", json={"qty": 0})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == ErrorCode.validation_error.value


@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_patch_unknown_line_is_404(
    seeded_db: SeededDb, persona_client: ContractClient
) -> None:
    """PATCHing a line id not in the caller's cart -> 404 not_found."""
    persona_client.get("/cart")  # ensure an open cart exists
    resp = persona_client.request(
        "PATCH", "/cart/items/00000000-0000-0000-0000-000000000000", json={"qty": 1}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == ErrorCode.not_found.value


# --------------------------------------------------------------------------- #
# DELETE /cart/items/{id}                                                      #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_delete_removes_line(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """DELETE removes the line and returns the (now empty) cart."""
    variant_id = handles.variant_ids["mug_in_stock"]
    added = persona_client.post(
        "/cart/items", json={"variant_id": variant_id, "qty": 2}
    ).json()["data"]
    item_id = added["items"][0]["id"]

    resp = persona_client.request("DELETE", f"/cart/items/{item_id}")
    assert resp.status_code == 200
    cart = resp.json()["data"]
    assert cart["items"] == []
    assert cart["item_count"] == 0
    assert cart["subtotal_minor"] == 0


# --------------------------------------------------------------------------- #
# Cross-user isolation                                                         #
# --------------------------------------------------------------------------- #
def test_cross_user_line_access_denied(
    seeded_db: SeededDb, api_client: ContractClient, handles: ResolvedHandles
) -> None:
    """A line in buyer A's cart is NOT addressable by buyer B (404, never 200/leak)."""
    variant_id = handles.variant_ids["mug_in_stock"]

    api_client.login(PERSONAS["buyer_primary"])
    added = api_client.post(
        "/cart/items", json={"variant_id": variant_id, "qty": 1}
    ).json()["data"]
    other_item_id = added["items"][0]["id"]

    api_client.login(PERSONAS["buyer_secondary"])  # switch identity (re-stash token)
    patch = api_client.request(
        "PATCH", f"/cart/items/{other_item_id}", json={"qty": 2}
    )
    assert patch.status_code == 404
    assert patch.json()["error"]["code"] == ErrorCode.not_found.value

    delete = api_client.request("DELETE", f"/cart/items/{other_item_id}")
    assert delete.status_code == 404
    assert delete.json()["error"]["code"] == ErrorCode.not_found.value


# --------------------------------------------------------------------------- #
# Auth                                                                          #
# --------------------------------------------------------------------------- #
def test_get_cart_unauthenticated_is_401(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    """No Bearer token -> 401 unauthenticated on the cart surface."""
    resp = api_client.get("/cart")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == ErrorCode.unauthenticated.value


def test_add_item_unauthenticated_is_401(
    seeded_db: SeededDb, api_client: ContractClient, handles: ResolvedHandles
) -> None:
    """No Bearer token on a write -> 401 unauthenticated."""
    resp = api_client.post(
        "/cart/items",
        json={"variant_id": handles.variant_ids["mug_in_stock"], "qty": 1},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == ErrorCode.unauthenticated.value
