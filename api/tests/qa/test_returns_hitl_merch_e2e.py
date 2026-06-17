"""Returns / HITL / merch-publish E2E — the J-SUP + J-SEL money-and-decision journey
(US-E7-02, deferred from Day 22).

WHAT THIS IS
============
A deterministic, KEY-FREE journey that walks the edge-path stories end-to-end against the
real ASGI app + seeded throwaway DB (and the merch ``nudges`` service for the publish
seam). It chains the steps a SUPPORT agent + a SELLER actually traverse, asserting the
CUMULATIVE invariants that only hold across the whole chain — not at any single boundary.

  (a) IN-WINDOW return request -> 201 created, within_window True (the buyer's happy edge).
  (b) OUT-OF-WINDOW fork (ADR-0043): the DIRECT buyer route past the 30-day window -> 409
      return_window_closed, while the AGENT service path (allow_hitl=True) on the SAME
      backdated order -> ``hitl_pending`` (deferred to a human, not refused). One test pins
      both halves of the fork so the divergence is provable in one place.
  (c) SUPPORT DECIDES -> the captured payment is actually flipped captured -> refunded
      (the money path runs, not just a status bump).
  (d) MERCH "PUBLISH" (ADR-0044): there is NO auto-publish — the seller-approved nudge
      ACCEPT is the publish seam. Accept RE-GROUNDS the price server-side, APPLIES it to
      the product's active variants, and writes a REVERSIBLE audit row carrying the prior
      prices (replaying it restores the pre-accept catalog).

LAYER SPLIT (deliberate — do NOT duplicate)
===========================================
Orion's ``tests/api/test_returns_handlers.py`` owns the per-endpoint atoms (each status +
envelope + role gate in isolation); Echo's ``tests/agent/test_seller_nudges.py`` owns the
nudge atoms (grounding, idempotency, injection-in-key). This module does NOT re-assert
those atoms. It is the JOURNEY layer: it chains request -> window-fork -> support-decide
-> refund-captured into ONE flow, and proves the merch accept is reversible as a publish
analog — the cross-step invariants the unit suites can't show.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Order, Payment, Product, Variant
from app.schemas.enums import PaymentStatus, ReturnReason
from app.schemas.returns import ReturnCreate, ReturnItemRequest
from app.schemas.seller import NudgeAcceptRequest
from app.services import nudges as nudges_service
from app.services import returns as returns_service
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


def _place_and_capture(
    client: ContractClient, variant_id: str, qty: int = 1
) -> dict:
    """Buyer: add -> checkout -> pay (captured), so there is real money to refund."""
    add = client.post("/cart/items", json={"variant_id": variant_id, "qty": qty})
    assert add.status_code == 201, add.text
    order = client.post("/orders", json={"ship_address": _SHIP}).json()["data"]
    intent = client.post(
        f"/orders/{order['id']}/payment-intent"
    ).json()["data"]
    pay = client.post(
        f"/orders/{order['id']}/payment-confirm",
        json={"payment_id": intent["payment_id"], "outcome": "captured"},
    )
    assert pay.status_code == 200, pay.text
    return order


# --------------------------------------------------------------------------- #
# (a)+(c) IN-WINDOW request -> support decides refunded -> payment captured->refunded.
# --------------------------------------------------------------------------- #
def test_in_window_return_support_decides_refund_captured(
    seeded_db: SeededDb, api_client: ContractClient, handles: ResolvedHandles
) -> None:
    """In-window request (201, within_window) -> support refunds -> payment flips to refunded."""
    api_client.login(PERSONAS["buyer_primary"])
    order = _place_and_capture(api_client, handles.variant_ids["mug_in_stock"], 1)

    # (a) In-window request: fresh order, within_window True.
    req = api_client.post(
        f"/orders/{order['id']}/returns",
        json={
            "reason_code": "damaged",
            "items": [{"order_item_id": order["items"][0]["id"], "qty": 1}],
        },
    )
    assert req.status_code == 201, req.text
    ret = req.json()["data"]
    assert ret["status"] == "requested"
    assert ret["within_window"] is True

    # Payment is captured BEFORE the decision.
    with Session(seeded_db.engine) as s:
        pay = s.scalar(select(Payment).where(Payment.order_id == order["id"]))
        assert pay is not None and pay.status == PaymentStatus.captured.value

    # (c) Support decides -> refunded; the money path actually runs.
    api_client.login(PERSONAS["support"])
    decided = api_client.request(
        "PATCH", f"/returns/{ret['id']}", json={"status": "refunded"}
    )
    assert decided.status_code == 200, decided.text
    body = decided.json()["data"]
    assert body["status"] == "refunded"
    assert body["resolved_at"] is not None

    with Session(seeded_db.engine) as s:
        pay = s.scalar(select(Payment).where(Payment.order_id == order["id"]))
        assert pay is not None
        assert pay.status == PaymentStatus.refunded.value  # captured -> refunded


# --------------------------------------------------------------------------- #
# (b) OUT-OF-WINDOW fork: direct -> 409; agent path (allow_hitl) -> hitl_pending. #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_out_of_window_direct_409_but_agent_path_hitl_pending(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """Backdated order: DIRECT route -> 409 closed; AGENT route (allow_hitl) -> hitl_pending.

    ADR-0043: a buyer's direct request past the window is a hard 409; the same request via
    the agent service (which sets ``allow_hitl=True``) is NOT refused — it is created as
    ``hitl_pending`` for a human to resolve. Pinning both on ONE backdated order proves the
    fork is the ``allow_hitl`` flag, not order state.
    """
    add = persona_client.post(
        "/cart/items", json={"variant_id": handles.variant_ids["mug_in_stock"], "qty": 1}
    )
    assert add.status_code == 201, add.text
    order = persona_client.post(
        "/orders", json={"ship_address": _SHIP}
    ).json()["data"]
    item_id = order["items"][0]["id"]

    # Backdate well past the 30-day window.
    with Session(seeded_db.engine) as s:
        row = s.get(Order, order["id"])
        assert row is not None
        row.placed_at = datetime.now(UTC) - timedelta(days=60)
        s.commit()

    # DIRECT buyer route -> 409 return_window_closed.
    direct = persona_client.post(
        f"/orders/{order['id']}/returns",
        json={"reason_code": "damaged", "items": [{"order_item_id": item_id, "qty": 1}]},
    )
    assert direct.status_code == 409, direct.text
    assert direct.json()["error"]["code"] == "return_window_closed"

    # AGENT service path on the SAME order -> hitl_pending (deferred, not refused).
    with Session(seeded_db.engine) as s:
        row = s.get(Order, order["id"])
        assert row is not None
        out, status = returns_service.request_return(
            s,
            row.user_id,
            order["id"],
            ReturnCreate(
                reason_code=ReturnReason.damaged,
                items=[ReturnItemRequest(order_item_id=item_id, qty=1)],
            ),
            allow_hitl=True,
        )
        s.commit()
    assert status == 201
    assert out.status.value == "hitl_pending"
    assert out.within_window is False


# --------------------------------------------------------------------------- #
# (d) MERCH PUBLISH analog: seller-approved nudge accept applies + is reversible. #
# --------------------------------------------------------------------------- #
def test_merch_nudge_accept_is_the_reversible_publish_seam(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """Accept = the publish seam: re-grounds, applies the price, and is fully reversible.

    ADR-0044: there is no auto-publish; the seller-approved nudge accept is what "publishes"
    a new price. This proves the publish contract end-to-end: the applied price equals the
    freshly RE-GROUNDED server-side median (not anything client-supplied), every active
    variant moves to it, and the reversible audit snapshot of prior prices replays cleanly
    back to the pre-accept catalog.
    """
    with Session(seeded_db.engine) as s:
        seller_id = handles.user_ids[PERSONAS["seller_ceramics"].handle]
        nudges = nudges_service.list_nudges(s, seller_id, cursor=None, limit=1).data
        assert nudges, "expected a grounded nudge for the ceramics seller"
        product_id = nudges[0].product_id

        # Independent re-ground -> the authoritative server-side target price.
        store_id = s.scalar(select(Product.store_id).where(Product.id == product_id))
        product = s.get(Product, product_id)
        assert product is not None
        grounded = nudges_service._ground_nudge(s, product=product, store_id=store_id)
        assert grounded is not None
        server_target = grounded[0].suggested_change["suggested_price_minor"]

        prior = {
            v.id: v.price_minor
            for v in s.scalars(
                select(Variant).where(
                    Variant.product_id == product_id, Variant.is_active.is_(True)
                )
            )
        }
        assert any(p != server_target for p in prior.values()), (
            "the nudge should move at least one variant off its current price"
        )

        # PUBLISH: accept the nudge.
        env = nudges_service.accept_nudge(
            s, seller_id, product_id, NudgeAcceptRequest()
        )
        s.commit()

        applied = env.data.suggested_change["suggested_price_minor"]
        assert applied == server_target  # re-grounded, NOT client-controlled
        for v in s.scalars(
            select(Variant).where(
                Variant.product_id == product_id, Variant.is_active.is_(True)
            )
        ):
            assert v.price_minor == server_target  # publish landed

        # REVERSIBLE: replay the audit snapshot restores the pre-publish catalog.
        from app.db.models import AgentAction

        action = s.scalars(
            select(AgentAction)
            .where(AgentAction.action_type == "merch_nudge_accept")
            .order_by(AgentAction.created_at.desc())
        ).first()
        assert action is not None
        assert action.payload["reversible"] is True
        recorded = action.payload["prior_variant_prices"]
        assert {str(k): v for k, v in prior.items()} == {
            str(k): v for k, v in recorded.items()
        }
        for vid, price in recorded.items():
            v = s.get(Variant, vid)
            assert v is not None
            v.price_minor = price
        s.flush()
        for v in s.scalars(select(Variant).where(Variant.product_id == product_id)):
            assert v.price_minor == prior[v.id]  # restored to pre-publish
