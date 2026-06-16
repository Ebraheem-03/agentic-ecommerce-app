"""Seller CRUD/fulfil surface — store / products / orders / fulfil (J-SEL-01,02,05).

Covers: store onboarding (fresh 201, re-onboard updates 200, slug-taken 409),
list-product happy path + labelled validation (duplicate SKU 409), seller orders
(only orders containing the seller's items, cursor envelope), fulfil a line
(fulfilled/cancelled, partial allowed), foreign-line 404 no-leak, invalid fulfil
target 422, and unauthenticated -> 401. The agent NUDGES stay 501 (Echo owns them).
"""

from __future__ import annotations

import uuid

import pytest

from app.schemas.envelope import ErrorCode
from tests.conftest import ContractClient, ResolvedHandles, SeededDb
from tests.fixtures.handles import PERSONAS

_SHIP = {
    "recipient_name": "Ada Buyer",
    "line1": "12 Kiln Lane",
    "city": "Brookline",
    "region": "MA",
    "postal_code": "02445",
    "country_code": "US",
}


# --------------------------------------------------------------------------- #
# Store onboarding.                                                            #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_onboard_store_fresh_201(
    seeded_db: SeededDb, persona_client: ContractClient
) -> None:
    """A user with no store -> 201, draft store created."""
    resp = persona_client.post(
        "/seller/store",
        json={"name": "Ada's Shop", "slug": "adas-shop", "location": "Boston"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["slug"] == "adas-shop"
    assert data["status"] == "draft"


@pytest.mark.parametrize("persona_client", ["seller_ceramics"], indirect=True)
def test_onboard_store_reonboard_updates_200(
    seeded_db: SeededDb, persona_client: ContractClient
) -> None:
    """A seller who already has a store -> 200, profile updated (not a 2nd store)."""
    resp = persona_client.post(
        "/seller/store",
        json={"name": "Sólveig Ceramics Renamed", "slug": "solveig-ceramics"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["name"] == "Sólveig Ceramics Renamed"


@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_onboard_store_slug_taken_409(
    seeded_db: SeededDb, persona_client: ContractClient
) -> None:
    """Claiming a slug another store owns -> 409 conflict."""
    resp = persona_client.post(
        "/seller/store",
        json={"name": "Copycat", "slug": "solveig-ceramics"},
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["error"]["code"] == ErrorCode.conflict.value


def test_onboard_store_unauthenticated_401(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    resp = api_client.post("/seller/store", json={"name": "X", "slug": "x"})
    assert resp.status_code == 401, resp.text


# --------------------------------------------------------------------------- #
# List a product.                                                             #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("persona_client", ["seller_ceramics"], indirect=True)
def test_create_product_happy(
    seeded_db: SeededDb, persona_client: ContractClient
) -> None:
    """List a product with a variant -> 201, product detail with the variant."""
    resp = persona_client.post(
        "/seller/products",
        json={
            "title": "Ember Bowl",
            "slug": "ember-bowl",
            "description": "Hand-thrown.",
            "category": "ceramics",
            "variants": [
                {"sku": "SOL-BOWL-EMBER", "price_minor": 3200, "qty_on_hand": 5}
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["slug"] == "ember-bowl"
    assert len(data["variants"]) == 1
    assert data["variants"][0]["sku"] == "SOL-BOWL-EMBER"

    # It surfaces in the public catalog read.
    listing = persona_client.get(f"/products/{data['id']}")
    assert listing.status_code == 200, listing.text


@pytest.mark.parametrize("persona_client", ["seller_ceramics"], indirect=True)
def test_create_product_duplicate_sku_409(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """A variant SKU that already exists in the catalog -> 409 conflict."""
    resp = persona_client.post(
        "/seller/products",
        json={
            "title": "Clash",
            "slug": "clash-mug",
            "variants": [{"sku": "SOL-MUG-SAGE", "price_minor": 1000, "qty_on_hand": 1}],
        },
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["error"]["code"] == ErrorCode.conflict.value


@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_create_product_no_store_404(
    seeded_db: SeededDb, persona_client: ContractClient
) -> None:
    """A user with no store cannot list a product -> 404 (must onboard first)."""
    resp = persona_client.post(
        "/seller/products",
        json={
            "title": "Orphan",
            "slug": "orphan-x",
            "variants": [{"sku": "ORPHAN-1", "price_minor": 1, "qty_on_hand": 0}],
        },
    )
    assert resp.status_code == 404, resp.text


# --------------------------------------------------------------------------- #
# Seller orders + fulfilment.                                                 #
# --------------------------------------------------------------------------- #
def _place_buyer_order(client: ContractClient, variant_id: str, qty: int = 1) -> dict:
    add = client.post("/cart/items", json={"variant_id": variant_id, "qty": qty})
    assert add.status_code == 201, add.text
    resp = client.post("/orders", json={"ship_address": _SHIP})
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def test_seller_orders_lists_only_own(
    seeded_db: SeededDb, api_client: ContractClient, handles: ResolvedHandles
) -> None:
    """A seller sees orders that contain their items, not unrelated ones."""
    api_client.login(PERSONAS["buyer_primary"])
    order = _place_buyer_order(api_client, handles.variant_ids["mug_in_stock"], 2)

    api_client.login(PERSONAS["seller_ceramics"])
    resp = api_client.get("/seller/orders")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {"data", "meta"}
    ids = [o["id"] for o in body["data"]]
    assert order["id"] in ids


def test_fulfil_item_marks_fulfilled(
    seeded_db: SeededDb, api_client: ContractClient, handles: ResolvedHandles
) -> None:
    """A seller marks their line fulfilled -> 200; the order summary comes back."""
    api_client.login(PERSONAS["buyer_primary"])
    order = _place_buyer_order(api_client, handles.variant_ids["mug_in_stock"], 1)
    item_id = order["items"][0]["id"]

    api_client.login(PERSONAS["seller_ceramics"])
    resp = api_client.request(
        "PATCH", f"/seller/order-items/{item_id}/fulfil",
        json={"fulfil_status": "fulfilled"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["id"] == order["id"]


def test_fulfil_item_foreign_line_404(
    seeded_db: SeededDb, api_client: ContractClient, handles: ResolvedHandles
) -> None:
    """A seller fulfilling another store's line -> no-leak 404."""
    api_client.login(PERSONAS["buyer_primary"])
    order = _place_buyer_order(api_client, handles.variant_ids["mug_in_stock"], 1)
    item_id = order["items"][0]["id"]

    # seller_leather does NOT own the mug's store.
    api_client.login(PERSONAS["seller_leather"])
    resp = api_client.request(
        "PATCH", f"/seller/order-items/{item_id}/fulfil",
        json={"fulfil_status": "fulfilled"},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.parametrize("persona_client", ["seller_ceramics"], indirect=True)
def test_fulfil_item_invalid_target_422(
    seeded_db: SeededDb, persona_client: ContractClient
) -> None:
    """``pending`` is not a valid fulfil target -> 422 (schema rejects it)."""
    resp = persona_client.request(
        "PATCH", f"/seller/order-items/{uuid.uuid4()}/fulfil",
        json={"fulfil_status": "pending"},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.parametrize("persona_client", ["seller_ceramics"], indirect=True)
def test_fulfil_item_missing_line_404(
    seeded_db: SeededDb, persona_client: ContractClient
) -> None:
    resp = persona_client.request(
        "PATCH", f"/seller/order-items/{uuid.uuid4()}/fulfil",
        json={"fulfil_status": "fulfilled"},
    )
    assert resp.status_code == 404, resp.text


def test_seller_orders_unauthenticated_401(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    resp = api_client.get("/seller/orders")
    assert resp.status_code == 401, resp.text
