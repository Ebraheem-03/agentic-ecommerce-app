"""Checkout E2E — the J-BUY-04 buy journey end-to-end (US-QA-D11).

LAYER SPLIT (read before adding cases here)
===========================================
Orion's ``tests/api/test_orders_handlers.py`` + ``test_cart_handlers.py`` are the
**handler-boundary** layer: each pins one endpoint's status + envelope + the single
state transition it owns (checkout reserves, capture decrements, decline releases,
empty-cart/out-of-stock/cross-user/401 edges) in isolation. Those atoms are NOT
re-asserted here.

THIS module is the **journey/E2E** layer for **J-BUY-04** (the buy journey from
``docs/qa/fixture-plan.md``): it chains the endpoints a buyer actually walks, against
the real ASGI app + the seeded throwaway DB (``seeded_db`` + ``persona_client``), and
asserts the *cumulative* inventory + lifecycle invariants the ADR-0028 state machine
guarantees across the WHOLE chain — not at any single boundary:

  * happy path: add-to-cart -> GET /cart reflects the line -> POST /orders (201,
    OrderDetail, snapshots frozen, source cart -> converted so the next GET /cart is a
    NEW empty cart) -> reserve-at-checkout (qty_reserved += qty, qty_on_hand untouched)
    -> payment-intent (pending) -> payment-confirm captured (qty_on_hand -= qty,
    qty_reserved restored) -> GET /orders + GET /orders/{id} show the captured payment.
  * deterministic decline: confirm failed -> 402 payment_declined, then the PERSISTED
    side effects (the decline commits-then-raises per ADR-0028 §5): payment row failed,
    reservation released, order still ``placed`` (unpaid, not cancelled).
  * idempotency: replaying POST /orders with the same Idempotency-Key returns the same
    order, creates no second order, and does NOT double-reserve.
  * out-of-stock: a line exceeding availability -> 409 out_of_stock, atomic (no order
    row, nothing reserved).
  * cross-user order access -> 404; unauthenticated -> 401.

Inventory state is read live from the seeded DB (variant -> inventory row) and variants
are resolved from the seed via ``handles`` (anti-drift) — no hardcoded counts. Error
assertions are pinned to the closed ``ErrorCode`` enum + HTTP status, never prose.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Inventory, Order
from app.schemas.envelope import ErrorCode
from tests.conftest import ContractClient, ResolvedHandles, SeededDb
from tests.fixtures.handles import PERSONAS

# AddressIn needs at least recipient_name + country_code; the rest is a realistic ship-to.
_SHIP = {
    "recipient_name": "Ada Buyer",
    "line1": "12 Kiln Lane",
    "city": "Brookline",
    "region": "MA",
    "postal_code": "02445",
    "country_code": "US",
}


def _inv(session: Session, variant_id: str) -> tuple[int, int]:
    """Live (qty_on_hand, qty_reserved) for a variant's inventory row."""
    inv = session.scalar(select(Inventory).where(Inventory.variant_id == variant_id))
    assert inv is not None, f"no inventory row for variant {variant_id}"
    return inv.qty_on_hand, inv.qty_reserved


def _order_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Order)) or 0


def _add_to_cart(client: ContractClient, variant_id: str, qty: int) -> None:
    resp = client.post("/cart/items", json={"variant_id": variant_id, "qty": qty})
    assert resp.status_code == 201, resp.text


# --------------------------------------------------------------------------- #
# J-BUY-04 happy path: the whole buy chain + reservation -> capture invariants #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_buy_journey_reserves_at_checkout_then_captures_on_pay(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """add -> cart -> checkout -> intent -> capture: stock reserved then sold, end to end."""
    variant_id = handles.variant_ids["mug_in_stock"]
    qty = 3
    with Session(seeded_db.engine) as s:
        on_hand_before, reserved_before = _inv(s, variant_id)

    # 1. Add to cart, then GET /cart reflects the line (the buyer sees what they'll buy).
    _add_to_cart(persona_client, variant_id, qty)
    cart = persona_client.get("/cart")
    assert cart.status_code == 200
    cart_body = cart.json()["data"]
    assert len(cart_body["items"]) == 1
    assert cart_body["items"][0]["variant_id"] == variant_id
    assert cart_body["items"][0]["qty"] == qty
    assert cart_body["item_count"] == qty

    # 2. Checkout -> 201 OrderDetail with frozen snapshots.
    co = persona_client.post("/orders", json={"ship_address": _SHIP})
    assert co.status_code == 201, co.text
    env = co.json()
    assert set(env.keys()) == {"data", "meta"}
    order = env["data"]
    order_id = order["id"]
    assert order["status"] == "placed"
    assert order["order_number"].startswith("HEA-")
    assert order["item_count"] == qty
    assert len(order["items"]) == 1
    line = order["items"][0]
    assert line["variant_id"] == variant_id
    assert line["qty"] == qty
    assert line["title_snapshot"]  # snapshots frozen at checkout
    assert line["store_name_snapshot"]
    assert order["total_minor"] == line["unit_price_minor"] * qty == order["subtotal_minor"]
    assert order["payments"] == []

    # 3. Reserve-at-checkout: qty_reserved bumped, qty_on_hand NOT yet drawn down.
    with Session(seeded_db.engine) as s:
        on_hand_post_co, reserved_post_co = _inv(s, variant_id)
    assert reserved_post_co == reserved_before + qty
    assert on_hand_post_co == on_hand_before

    # 4. Source cart converted -> a fresh GET /cart yields a NEW empty cart.
    fresh = persona_client.get("/cart")
    assert fresh.status_code == 200
    fresh_cart = fresh.json()["data"]
    assert fresh_cart["items"] == []
    assert fresh_cart["id"] != cart_body["id"]

    # 5. Payment-intent -> 201 pending, amount == order total.
    pi = persona_client.post(f"/orders/{order_id}/payment-intent")
    assert pi.status_code == 201, pi.text
    intent = pi.json()["data"]
    assert intent["status"] == "pending"
    assert intent["amount_minor"] == order["total_minor"]

    # 6. Confirm captured -> 200; qty_on_hand decremented AND qty_reserved restored.
    pc = persona_client.post(
        f"/orders/{order_id}/payment-confirm",
        json={"payment_id": intent["payment_id"], "outcome": "captured"},
    )
    assert pc.status_code == 200, pc.text
    assert pc.json()["data"]["status"] == "captured"
    with Session(seeded_db.engine) as s:
        on_hand_final, reserved_final = _inv(s, variant_id)
    assert on_hand_final == on_hand_before - qty  # sold
    assert reserved_final == reserved_before  # reservation released into the sale

    # 7. GET /orders + GET /orders/{id} show the order with the captured payment.
    listing = persona_client.get("/orders")
    assert listing.status_code == 200
    assert order_id in [o["id"] for o in listing.json()["data"]]

    detail = persona_client.get(f"/orders/{order_id}")
    assert detail.status_code == 200
    dbody = detail.json()["data"]
    assert dbody["id"] == order_id
    assert dbody["status"] == "placed"
    assert any(p["status"] == "captured" for p in dbody["payments"])


# --------------------------------------------------------------------------- #
# Deterministic decline: 402, persisted side effects, order stays placed        #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_buy_journey_decline_releases_reservation_and_keeps_order_placed(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """confirm failed -> 402 payment_declined; release + payment=failed PERSIST; order placed."""
    variant_id = handles.variant_ids["mug_in_stock"]
    qty = 2
    with Session(seeded_db.engine) as s:
        on_hand_before, reserved_before = _inv(s, variant_id)

    _add_to_cart(persona_client, variant_id, qty)
    order = persona_client.post("/orders", json={"ship_address": _SHIP}).json()["data"]
    order_id = order["id"]
    intent = persona_client.post(f"/orders/{order_id}/payment-intent").json()["data"]

    pc = persona_client.post(
        f"/orders/{order_id}/payment-confirm",
        json={"payment_id": intent["payment_id"], "outcome": "failed"},
    )
    assert pc.status_code == 402
    assert pc.json()["error"]["code"] == ErrorCode.payment_declined.value

    # PERSISTED despite the raised 402 (commit-then-raise, ADR-0028 §5): reservation
    # released back to baseline, on_hand untouched (no sale happened).
    with Session(seeded_db.engine) as s:
        on_hand_after, reserved_after = _inv(s, variant_id)
    assert reserved_after == reserved_before
    assert on_hand_after == on_hand_before

    # Order stays placed (unpaid, not cancelled) and the failed payment row persisted.
    detail = persona_client.get(f"/orders/{order_id}").json()["data"]
    assert detail["status"] == "placed"
    assert any(p["status"] == "failed" for p in detail["payments"])


# --------------------------------------------------------------------------- #
# Idempotency: replay same key -> same order, no second order, no double-reserve #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_checkout_idempotency_no_double_order_or_reservation(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """Replaying POST /orders with one Idempotency-Key returns the same order, reserves once."""
    variant_id = handles.variant_ids["mug_in_stock"]
    qty = 2
    with Session(seeded_db.engine) as s:
        orders_before = _order_count(s)
        _, reserved_before = _inv(s, variant_id)

    _add_to_cart(persona_client, variant_id, qty)
    key = str(uuid.uuid4())

    first = persona_client.post(
        "/orders", json={"ship_address": _SHIP}, headers={"Idempotency-Key": key}
    )
    second = persona_client.post(
        "/orders", json={"ship_address": _SHIP}, headers={"Idempotency-Key": key}
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["data"]["id"] == second.json()["data"]["id"]

    with Session(seeded_db.engine) as s:
        assert _order_count(s) == orders_before + 1  # exactly one new order
        _, reserved_after = _inv(s, variant_id)
    assert reserved_after == reserved_before + qty  # reserved once, not twice


# --------------------------------------------------------------------------- #
# Out-of-stock: 409, atomic — no order row, nothing reserved                    #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_checkout_out_of_stock_is_atomic(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """A checkout line exceeding availability -> 409 out_of_stock; no order, no reservation."""
    variant_id = handles.variant_ids["mug_low_stock"]
    with Session(seeded_db.engine) as s:
        orders_before = _order_count(s)
        on_hand_before, reserved_before = _inv(s, variant_id)
        avail = on_hand_before - reserved_before

    # Add the low-stock line right at availability (passes the cart guard), then drain
    # availability out-of-band so checkout's FOR UPDATE re-check finds a shortfall.
    _add_to_cart(persona_client, variant_id, avail)
    with Session(seeded_db.engine) as s:
        inv = s.scalar(select(Inventory).where(Inventory.variant_id == variant_id))
        assert inv is not None
        inv.qty_reserved = inv.qty_on_hand  # zero availability
        s.commit()

    resp = persona_client.post("/orders", json={"ship_address": _SHIP})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == ErrorCode.out_of_stock.value

    # Atomic: no order row created, and our out-of-band reservation is the only delta
    # (the checkout reserved nothing).
    with Session(seeded_db.engine) as s:
        assert _order_count(s) == orders_before
        on_hand_after, reserved_after = _inv(s, variant_id)
    assert on_hand_after == on_hand_before
    assert reserved_after == on_hand_before  # only the out-of-band bump, none from checkout


# --------------------------------------------------------------------------- #
# Cross-user order access -> 404 (never leak existence)                         #
# --------------------------------------------------------------------------- #
def test_cross_user_order_access_is_404(
    seeded_db: SeededDb, api_client: ContractClient, handles: ResolvedHandles
) -> None:
    """Buyer B cannot read buyer A's order -> 404 not_found."""
    variant_id = handles.variant_ids["mug_in_stock"]
    api_client.login(PERSONAS["buyer_primary"])
    api_client.post("/cart/items", json={"variant_id": variant_id, "qty": 1})
    order_id = api_client.post("/orders", json={"ship_address": _SHIP}).json()["data"]["id"]

    api_client.login(PERSONAS["buyer_secondary"])
    resp = api_client.get(f"/orders/{order_id}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == ErrorCode.not_found.value


# --------------------------------------------------------------------------- #
# Unauthenticated checkout -> 401                                               #
# --------------------------------------------------------------------------- #
def test_checkout_unauthenticated_is_401(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    """No Bearer token on checkout -> 401 unauthenticated."""
    resp = api_client.post("/orders", json={"ship_address": _SHIP})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == ErrorCode.unauthenticated.value
