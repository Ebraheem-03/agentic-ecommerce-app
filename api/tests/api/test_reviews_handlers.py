"""Product reviews — list + create with rating rollup (J-BUY-02).

Covers: create happy path (201 + rollup recompute on product detail), one-per-user
uniqueness (409 duplicate_review), list newest-first, missing-product 404, and
unauthenticated create -> 401.
"""

from __future__ import annotations

import uuid

import pytest

from app.schemas.envelope import ErrorCode
from tests.conftest import ContractClient, ResolvedHandles, SeededDb
from tests.fixtures.handles import PERSONAS


@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_create_review_and_rollup(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """Create a review -> 201; product detail rating_avg/count reflect it."""
    product_id = handles.product_ids["belt"]
    resp = persona_client.post(
        f"/products/{product_id}/reviews",
        json={"rating": 4, "title": "Lovely", "body": "Great mug."},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["rating"] == 4
    assert data["product_id"] == product_id

    detail = persona_client.get(f"/products/{product_id}").json()["data"]
    assert detail["rating_count"] >= 1
    assert detail["rating_avg"] is not None


@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_create_review_duplicate_409(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """A second review by the same user on the same product -> 409 duplicate_review."""
    product_id = handles.product_ids["belt"]
    first = persona_client.post(
        f"/products/{product_id}/reviews", json={"rating": 5, "body": "First."}
    )
    assert first.status_code == 201, first.text
    second = persona_client.post(
        f"/products/{product_id}/reviews", json={"rating": 3, "body": "Second."}
    )
    assert second.status_code == 409, second.text
    assert second.json()["error"]["code"] == ErrorCode.duplicate_review.value


def test_list_reviews_newest_first(
    seeded_db: SeededDb, api_client: ContractClient, handles: ResolvedHandles
) -> None:
    """Two buyers review one product; list returns newest first, envelope shape holds."""
    product_id = handles.product_ids["belt"]

    api_client.login(PERSONAS["buyer_primary"])
    api_client.post(f"/products/{product_id}/reviews", json={"rating": 4, "body": "A"})
    api_client.login(PERSONAS["buyer_secondary"])
    api_client.post(f"/products/{product_id}/reviews", json={"rating": 2, "body": "B"})

    resp = api_client.get(f"/products/{product_id}/reviews")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {"data", "meta"}
    assert len(body["data"]) == 2
    # Newest first: the second (buyer_secondary, "B") comes first.
    assert body["data"][0]["body"] == "B"


@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_create_review_missing_product_404(
    seeded_db: SeededDb, persona_client: ContractClient
) -> None:
    resp = persona_client.post(
        f"/products/{uuid.uuid4()}/reviews", json={"rating": 4, "body": "x"}
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["error"]["code"] == ErrorCode.not_found.value


def test_list_reviews_missing_product_404(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    resp = api_client.get(f"/products/{uuid.uuid4()}/reviews")
    assert resp.status_code == 404, resp.text


def test_create_review_unauthenticated_401(
    seeded_db: SeededDb, api_client: ContractClient, handles: ResolvedHandles
) -> None:
    resp = api_client.post(
        f"/products/{handles.product_ids['mug']}/reviews",
        json={"rating": 4, "body": "x"},
    )
    assert resp.status_code == 401, resp.text
