"""Tool EXECUTION tests — validation, scope, idempotency, retry, audit (US-E5-02).

DB-backed against the seeded throwaway DB (the ``seeded_db`` + ``handles`` spine). These
call ``execute_tool`` directly with a real ``Session`` and a real seeded ``User`` —
identity is resolved the same way HTTP handlers resolve it, so there is one path for
humans and agents.

LAYER SPLIT: Echo's tests here prove the executor's CROSS-CUTTING behavior (validate /
scope / idempotency replay / retry exhaustion / audit row) plus a happy path per tool.
Juno owns the exhaustive per-tool behavioral E2E matrix in US-QA-D12.
"""

from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.executor import (
    RetryPolicy,
    TransientToolError,
    _run_with_retry,
    execute_tool,
)
from app.agent.tools import (
    CouponDiscountOut,
    DraftOrderOutput,
    InventoryOutput,
    RefundOutput,
    ToolName,
)
from app.core.errors import APIError
from app.db.models import AgentAction, Payment, User
from app.schemas.cart import CartOut
from app.schemas.enums import AgentOutcome, PaymentStatus
from app.schemas.envelope import ErrorCode
from app.schemas.order import OrderDetail
from tests.conftest import ResolvedHandles, SeededDb
from tests.fixtures.handles import PERSONAS

_SHIP = {
    "recipient_name": "Ada Buyer",
    "line1": "12 Kiln Lane",
    "city": "Brookline",
    "region": "MA",
    "postal_code": "02445",
    "country_code": "US",
}


def _user(session: Session, handles: ResolvedHandles, persona: str) -> User:
    uid = handles.user_ids[PERSONAS[persona].handle]
    user = session.get(User, uid)
    assert user is not None
    return user


def _actions(session: Session, name: ToolName) -> list[AgentAction]:
    return list(
        session.scalars(
            select(AgentAction).where(AgentAction.action_type == name.value)
        )
    )


# --------------------------------------------------------------------------- #
# Read tools — happy path + audit.                                             #
# --------------------------------------------------------------------------- #
def test_search_executes_and_audits(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        res = execute_tool(
            ToolName.search, {"query": "mug", "limit": 5}, session=s, user=user
        )
        assert res.status_code == 200
        assert res.name is ToolName.search
        # an applied audit row landed
        rows = _actions(s, ToolName.search)
        assert len(rows) == 1
        assert rows[0].outcome == AgentOutcome.applied.value
        assert rows[0].actor_user_id == user.id


def test_product_details_and_inventory(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        slug = "tide-pour-over-mug"
        det = execute_tool(
            ToolName.product_details, {"id_or_slug": slug}, session=s, user=user
        )
        assert det.status_code == 200
        inv = execute_tool(
            ToolName.inventory, {"product_id_or_slug": slug}, session=s, user=user
        )
        assert inv.status_code == 200
        assert cast(InventoryOutput, inv.output).any_in_stock in (True, False)


def test_apply_coupon_known_and_unknown(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        ok = execute_tool(
            ToolName.apply_coupon,
            {"code": "WELCOME10", "subtotal_minor": 5000},
            session=s,
            user=user,
        )
        assert cast(CouponDiscountOut, ok.output).discount_minor == 500  # 10% of 5000
        with pytest.raises(APIError) as ei:
            execute_tool(
                ToolName.apply_coupon,
                {"code": "NOPE", "subtotal_minor": 5000},
                session=s,
                user=user,
            )
        assert ei.value.code is ErrorCode.not_found


# --------------------------------------------------------------------------- #
# Validation — 422 with per-field details + refused audit.                     #
# --------------------------------------------------------------------------- #
def test_validation_error_audited_as_refused(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        with pytest.raises(APIError) as ei:
            execute_tool(ToolName.search, {"query": ""}, session=s, user=user)
        assert ei.value.status_code == 422
        assert ei.value.code is ErrorCode.validation_error
        assert ei.value.details is not None and "errors" in ei.value.details
        rows = _actions(s, ToolName.search)
        assert len(rows) == 1 and rows[0].outcome == AgentOutcome.refused.value


# --------------------------------------------------------------------------- #
# addToCart — mutating happy path + idempotent replay.                         #
# --------------------------------------------------------------------------- #
def test_add_to_cart_and_idempotent_replay(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        variant = handles.variant_ids["mug_in_stock"]
        first = execute_tool(
            ToolName.add_to_cart,
            {"variant_id": variant, "qty": 2},
            session=s,
            user=user,
            idempotency_key="k-add-1",
        )
        assert first.status_code == 201
        assert first.replayed is False
        assert cast(CartOut, first.output).item_count == 2

        # Same key -> replay the stored cart, NOT a second increment.
        again = execute_tool(
            ToolName.add_to_cart,
            {"variant_id": variant, "qty": 2},
            session=s,
            user=user,
            idempotency_key="k-add-1",
        )
        assert again.replayed is True
        # not 4 — replayed, not re-applied
        assert cast(CartOut, again.output).item_count == 2


# --------------------------------------------------------------------------- #
# draftOrder — checkout + intent without confirming payment.                   #
# --------------------------------------------------------------------------- #
def test_draft_order_places_order_and_intent(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        variant = handles.variant_ids["mug_in_stock"]
        execute_tool(
            ToolName.add_to_cart,
            {"variant_id": variant, "qty": 1},
            session=s,
            user=user,
        )
        res = execute_tool(
            ToolName.draft_order, {"ship_address": _SHIP}, session=s, user=user
        )
        draft = cast(DraftOrderOutput, res.output)
        assert res.status_code == 201
        assert draft.order.status == "placed"
        assert draft.payment_intent.status == PaymentStatus.pending
        # payment not confirmed — order is placed (unpaid)
        order_id = draft.order.id

        st = execute_tool(
            ToolName.order_status, {"order_id": order_id}, session=s, user=user
        )
        assert cast(OrderDetail, st.output).status == "placed"


# --------------------------------------------------------------------------- #
# orderStatus / refund cross-user scope — no leak (404 / 403 policy).          #
# --------------------------------------------------------------------------- #
def test_order_status_cross_user_is_not_found(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        owner = _user(s, handles, "buyer_primary")
        other = _user(s, handles, "buyer_secondary")
        variant = handles.variant_ids["mug_in_stock"]
        execute_tool(
            ToolName.add_to_cart,
            {"variant_id": variant, "qty": 1},
            session=s,
            user=owner,
        )
        draft = execute_tool(
            ToolName.draft_order, {"ship_address": _SHIP}, session=s, user=owner
        )
        order_id = cast(DraftOrderOutput, draft.output).order.id

        # A different buyer asking for the owner's order -> not_found (no leak).
        with pytest.raises(APIError) as ei:
            execute_tool(
                ToolName.order_status,
                {"order_id": order_id},
                session=s,
                user=other,
            )
        assert ei.value.code is ErrorCode.not_found


def test_refund_owner_and_privileged_and_foreign(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        owner = _user(s, handles, "buyer_primary")
        other = _user(s, handles, "buyer_secondary")
        support = _user(s, handles, "support")
        variant = handles.variant_ids["mug_in_stock"]

        execute_tool(
            ToolName.add_to_cart,
            {"variant_id": variant, "qty": 1},
            session=s,
            user=owner,
        )
        draft_res = execute_tool(
            ToolName.draft_order, {"ship_address": _SHIP}, session=s, user=owner
        )
        draft = cast(DraftOrderOutput, draft_res.output)
        order_id = draft.order.id
        payment_id = draft.payment_intent.payment_id

        # No captured payment yet -> 409 conflict.
        with pytest.raises(APIError) as ei:
            execute_tool(
                ToolName.refund, {"order_id": order_id}, session=s, user=owner
            )
        assert ei.value.code is ErrorCode.conflict

        # Capture the payment so there's something to refund.
        order_service_capture(s, owner.id, order_id, payment_id)

        # A foreign buyer refunding the owner's order -> not_found (no leak).
        with pytest.raises(APIError) as ei2:
            execute_tool(
                ToolName.refund, {"order_id": order_id}, session=s, user=other
            )
        assert ei2.value.code is ErrorCode.not_found

        # Support (privileged) may refund any order.
        res = execute_tool(
            ToolName.refund,
            {"order_id": order_id, "reason": "goodwill"},
            session=s,
            user=support,
        )
        assert cast(RefundOutput, res.output).payment.status == PaymentStatus.refunded
        pay = s.get(Payment, payment_id)
        assert pay is not None and pay.status == PaymentStatus.refunded.value


def order_service_capture(
    session: Session, user_id: str, order_id: str, payment_id: str
) -> None:
    """Confirm the mock payment to ``captured`` so a refund has something to act on."""
    from app.services import orders as order_service

    # Shared-session: drop cached ORM collections so confirm sees the flushed payment
    # (the executor does this per tool call; this helper calls the service directly).
    session.expire_all()
    order_service.confirm_payment(
        session,
        user_id,
        order_id,
        payment_id=payment_id,
        outcome=PaymentStatus.captured,
        idempotency_key=None,
    )


# --------------------------------------------------------------------------- #
# Retry / timeout policy — deterministic, injected clock.                      #
# --------------------------------------------------------------------------- #
def test_retry_exhaustion_raises_rate_limited() -> None:
    calls = {"n": 0}

    def _always_transient() -> int:
        calls["n"] += 1
        raise TransientToolError("flaky")

    policy = RetryPolicy(max_attempts=3, timeout_s=100.0, backoff_s=0.0)
    with pytest.raises(APIError) as ei:
        _run_with_retry(
            _always_transient, policy=policy, clock=lambda: 0.0, sleep=lambda _: None
        )
    assert ei.value.code is ErrorCode.rate_limited
    assert calls["n"] == 3  # all attempts used


def test_retry_succeeds_after_transient() -> None:
    calls = {"n": 0}

    def _flaky_once() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise TransientToolError("flaky")
        return "ok"

    policy = RetryPolicy(max_attempts=3, timeout_s=100.0, backoff_s=0.0)
    out = _run_with_retry(
        _flaky_once, policy=policy, clock=lambda: 0.0, sleep=lambda _: None
    )
    assert out == "ok"
    assert calls["n"] == 2


def test_domain_apierror_is_not_retried() -> None:
    calls = {"n": 0}

    def _refuses() -> int:
        calls["n"] += 1
        raise APIError(404, ErrorCode.not_found, "nope")

    policy = RetryPolicy(max_attempts=3, timeout_s=100.0, backoff_s=0.0)
    with pytest.raises(APIError) as ei:
        _run_with_retry(_refuses, policy=policy, clock=lambda: 0.0, sleep=lambda _: None)
    assert ei.value.code is ErrorCode.not_found
    assert calls["n"] == 1  # definitive — never retried


def test_per_attempt_timeout_overrun_rate_limited() -> None:
    ticks = iter([0.0, 50.0])  # start, end -> 50s elapsed > 10s timeout

    def _slow() -> str:
        return "done"

    policy = RetryPolicy(max_attempts=2, timeout_s=10.0, backoff_s=0.0)
    with pytest.raises(APIError) as ei:
        _run_with_retry(
            _slow, policy=policy, clock=lambda: next(ticks), sleep=lambda _: None
        )
    assert ei.value.code is ErrorCode.rate_limited
