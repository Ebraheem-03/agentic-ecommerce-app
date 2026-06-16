"""Returns surface — request / list / get / decide (US-E6, J-BUY-06 / J-SUP-03).

DB-backed handler behavior against the seeded throwaway DB via the ``seeded_db`` +
``persona_client`` spine. Covers: request happy path (201, within_window True), the
out-of-window DIRECT path (409 return_window_closed) vs the agent service path
(allow_hitl -> hitl_pending), foreign-order 404 no-leak, item validation (foreign
order_item -> 422), list scoping (buyer own vs support all), get no-leak, decide
approve/reject + role gate (403), decide refunded reuses the payment refund, and
unauthenticated -> 401.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Order, Payment
from app.schemas.enums import PaymentStatus, ReturnReason
from app.schemas.envelope import ErrorCode
from app.schemas.returns import ReturnCreate, ReturnItemRequest
from app.services import returns as returns_service
from tests.conftest import ContractClient, ResolvedHandles, SeededDb

_SHIP = {
    "recipient_name": "Ada Buyer",
    "line1": "12 Kiln Lane",
    "city": "Brookline",
    "region": "MA",
    "postal_code": "02445",
    "country_code": "US",
}


def _place_order(client: ContractClient, variant_id: str, qty: int = 1) -> dict:
    """Add to cart + checkout; return the OrderDetail dict."""
    resp = client.post("/cart/items", json={"variant_id": variant_id, "qty": qty})
    assert resp.status_code == 201, resp.text
    resp = client.post("/orders", json={"ship_address": _SHIP})
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


# --------------------------------------------------------------------------- #
# Request a return.                                                            #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_request_return_within_window(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """A fresh order is within window -> 201, status requested, within_window True."""
    order = _place_order(persona_client, handles.variant_ids["mug_in_stock"], 2)
    item_id = order["items"][0]["id"]

    resp = persona_client.post(
        f"/orders/{order['id']}/returns",
        json={"reason_code": "damaged", "items": [{"order_item_id": item_id, "qty": 1}]},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["status"] == "requested"
    assert data["within_window"] is True
    assert data["order_id"] == order["id"]
    assert len(data["items"]) == 1
    assert data["items"][0]["order_item_id"] == item_id


@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_request_return_out_of_window_direct_409(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """DIRECT path past the window -> 409 return_window_closed (locked contract)."""
    order = _place_order(persona_client, handles.variant_ids["mug_in_stock"], 1)
    item_id = order["items"][0]["id"]

    # Backdate placed_at well past the 30-day window.
    with Session(seeded_db.engine) as s:
        row = s.get(Order, order["id"])
        assert row is not None
        row.placed_at = datetime.now(UTC) - timedelta(days=60)
        s.commit()

    resp = persona_client.post(
        f"/orders/{order['id']}/returns",
        json={"reason_code": "damaged", "items": [{"order_item_id": item_id, "qty": 1}]},
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["error"]["code"] == ErrorCode.return_window_closed.value


@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_request_return_out_of_window_agent_hitl(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """AGENT path (allow_hitl=True) past the window -> hitl_pending, not a 409."""
    order = _place_order(persona_client, handles.variant_ids["mug_in_stock"], 1)
    item_id = order["items"][0]["id"]

    with Session(seeded_db.engine) as s:
        row = s.get(Order, order["id"])
        assert row is not None
        row.placed_at = datetime.now(UTC) - timedelta(days=60)
        s.commit()

        body = ReturnCreate(
            reason_code=ReturnReason.damaged,
            items=[ReturnItemRequest(order_item_id=item_id, qty=1)],
        )
        out, status = returns_service.request_return(
            s, row.user_id, order["id"], body, allow_hitl=True
        )
        s.commit()

    assert status == 201
    assert out.status.value == "hitl_pending"
    assert out.within_window is False


@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_request_return_foreign_order_404(
    seeded_db: SeededDb, persona_client: ContractClient
) -> None:
    """A return on someone else's / nonexistent order is a no-leak 404."""
    resp = persona_client.post(
        f"/orders/{uuid.uuid4()}/returns",
        json={"reason_code": "damaged", "items": [{"order_item_id": str(uuid.uuid4()), "qty": 1}]},
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["error"]["code"] == ErrorCode.not_found.value


@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_request_return_foreign_item_422(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """A return line referencing an item not on this order -> 422 validation_error."""
    order = _place_order(persona_client, handles.variant_ids["mug_in_stock"], 1)
    resp = persona_client.post(
        f"/orders/{order['id']}/returns",
        json={"reason_code": "damaged", "items": [{"order_item_id": str(uuid.uuid4()), "qty": 1}]},
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == ErrorCode.validation_error.value


def test_request_return_unauthenticated_401(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    resp = api_client.post(
        f"/orders/{uuid.uuid4()}/returns",
        json={"reason_code": "damaged", "items": [{"order_item_id": str(uuid.uuid4()), "qty": 1}]},
    )
    assert resp.status_code == 401, resp.text


# --------------------------------------------------------------------------- #
# List + get scoping.                                                          #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_list_returns_buyer_sees_own(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    order = _place_order(persona_client, handles.variant_ids["mug_in_stock"], 1)
    item_id = order["items"][0]["id"]
    persona_client.post(
        f"/orders/{order['id']}/returns",
        json={"reason_code": "damaged", "items": [{"order_item_id": item_id, "qty": 1}]},
    )
    resp = persona_client.get("/returns")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {"data", "meta"}
    assert len(body["data"]) == 1
    assert body["data"][0]["order_id"] == order["id"]


@pytest.mark.parametrize("persona_client", ["buyer_secondary"], indirect=True)
def test_get_return_foreign_404(
    seeded_db: SeededDb, persona_client: ContractClient
) -> None:
    """A buyer fetching a return id they don't own -> no-leak 404."""
    resp = persona_client.get(f"/returns/{uuid.uuid4()}")
    assert resp.status_code == 404, resp.text


# --------------------------------------------------------------------------- #
# Decide.                                                                      #
# --------------------------------------------------------------------------- #
def _seed_return(client: ContractClient, handles: ResolvedHandles) -> str:
    order = _place_order(client, handles.variant_ids["mug_in_stock"], 1)
    item_id = order["items"][0]["id"]
    resp = client.post(
        f"/orders/{order['id']}/returns",
        json={"reason_code": "damaged", "items": [{"order_item_id": item_id, "qty": 1}]},
    )
    return resp.json()["data"]["id"]


@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_decide_return_buyer_forbidden(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """A buyer cannot decide a return -> 403 forbidden (support/admin only)."""
    return_id = _seed_return(persona_client, handles)
    resp = persona_client.request(
        "PATCH", f"/returns/{return_id}", json={"status": "approved"}
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == ErrorCode.forbidden.value


def test_decide_return_support_approves(
    seeded_db: SeededDb, api_client: ContractClient, handles: ResolvedHandles
) -> None:
    """Support approves a buyer's return -> 200, status approved, approved_by + resolved_at set."""
    from tests.fixtures.handles import PERSONAS

    api_client.login(PERSONAS["buyer_primary"])
    return_id = _seed_return(api_client, handles)

    api_client.login(PERSONAS["support"])
    resp = api_client.request(
        "PATCH", f"/returns/{return_id}", json={"status": "approved"}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "approved"
    assert data["approved_by"] is not None
    assert data["resolved_at"] is not None


def test_decide_return_refunded_reuses_payment_refund(
    seeded_db: SeededDb, api_client: ContractClient, handles: ResolvedHandles
) -> None:
    """A refunded decision flips the captured payment -> refunded (shared refund path)."""
    from tests.fixtures.handles import PERSONAS

    api_client.login(PERSONAS["buyer_primary"])
    order = _place_order(api_client, handles.variant_ids["mug_in_stock"], 1)
    # Pay for the order so there's a captured payment to refund.
    intent = api_client.post(f"/orders/{order['id']}/payment-intent").json()["data"]
    pay = api_client.post(
        f"/orders/{order['id']}/payment-confirm",
        json={"payment_id": intent["payment_id"], "outcome": "captured"},
    )
    assert pay.status_code == 200, pay.text
    item_id = order["items"][0]["id"]
    ret = api_client.post(
        f"/orders/{order['id']}/returns",
        json={"reason_code": "damaged", "items": [{"order_item_id": item_id, "qty": 1}]},
    ).json()["data"]

    api_client.login(PERSONAS["support"])
    resp = api_client.request(
        "PATCH", f"/returns/{ret['id']}", json={"status": "refunded"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "refunded"

    with Session(seeded_db.engine) as s:
        payment = s.scalar(select(Payment).where(Payment.order_id == order["id"]))
        assert payment is not None
        assert payment.status == PaymentStatus.refunded.value
