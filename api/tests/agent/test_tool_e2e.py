"""Tool-call E2E matrix — exhaustive per-tool success / validation / unauthorized (US-QA-D12).

DB-backed against the seeded throwaway DB (the ``seeded_db`` + ``handles`` spine,
``tests/conftest.py``). Every test drives ``execute_tool`` directly with a real
``Session`` and a real seeded ``User`` — identity is resolved the SAME way HTTP handlers
resolve it (``require_user`` / ``require_role``), so there is one path for humans and
agents (ADR-0029 §2).

LAYER SPLIT (don't re-assert the atoms below):
  * ``test_tool_schemas.py``  (Echo, US-E5-01) — schema generation + example parsing +
    serializable provider spec, at the registry boundary.
  * ``test_tool_executor.py`` (Echo, US-E5-02) — the executor's CROSS-CUTTING behaviour
    (validate / scope / one idempotency replay / retry exhaustion + timeout / one audit
    row) plus ONE happy path per tool.
  * THIS module (Juno, US-QA-D12) — the exhaustive per-tool behavioural matrix
    (success x validation-failure x unauthorized for all 8 tools) plus the journey-level
    cross-cutting behaviours: idempotency effect-once, retry-doesn't-double-apply,
    domain-error-not-retried-inside-execute_tool, and the audit ``applied``/``refused``
    outcome per terminal call. Assertions pin to closed ``ErrorCode`` + status, never
    prose, and assert the REAL effect (cart line / placed order + intent + reserved
    stock / refunded payment), not just a status code.

SHARED-SESSION GOTCHA (Echo): ``execute_tool`` calls ``session.expire_all()`` per call
(the agent layer shares one long-lived session). Tests that read ORM state directly on
that shared session to assert an effect must re-query / let the expire happen so they
don't assert a stale identity-mapped collection. Helpers here ``expire_all()`` before a
direct service/ORM read for exactly this reason.

CONTRACT NOTES surfaced for Atlas (not failures — the layer is asserted AS BUILT):
  * ``execute_tool`` takes a NON-optional ``User``: the "no identity" unauth case is
    enforced upstream at ``require_user`` (the deps boundary), not inside the executor.
    The executor-level unauthorized surface is therefore cross-user RESOURCE access
    (foreign order/cart -> ``not_found``, no leak) and the ``refund`` ownership gate.
  * ``_check_scope`` is a no-op today (ADR-0029 §3 + [REVIEW] fork): a non-owner,
    non-privileged ``refund`` surfaces as ``not_found`` (no-leak), NOT ``403 forbidden``.
    No caller can currently produce a ``forbidden`` from this layer; the 403 seam exists
    but is dormant pending the guardrail-policy decision. Documented, asserted as built.
"""

from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.executor import (
    RetryPolicy,
    ToolResult,
    TransientToolError,
    execute_tool,
)
from app.agent.tools import (
    CouponDiscountOut,
    DraftOrderOutput,
    InventoryOutput,
    RefundOutput,
    SearchOutput,
    ToolName,
)
from app.core.errors import APIError
from app.db.models import AgentAction, Inventory, Payment, User
from app.schemas.cart import CartOut
from app.schemas.catalog import ProductDetail
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

# A well-formed UUID that does not exist in the seed — for "not found, no leak" reads.
_GHOST_UUID = "00000000-0000-4000-8000-000000000000"
_MUG_SLUG = "tide-pour-over-mug"


# --------------------------------------------------------------------------- #
# Helpers.                                                                     #
# --------------------------------------------------------------------------- #
def _user(session: Session, handles: ResolvedHandles, persona: str) -> User:
    uid = handles.user_ids[PERSONAS[persona].handle]
    user = session.get(User, uid)
    assert user is not None
    return user


def _actions(session: Session, name: ToolName) -> list[AgentAction]:
    """All audit rows for one tool, oldest-first (insertion order via created_at)."""
    return list(
        session.scalars(
            select(AgentAction)
            .where(AgentAction.action_type == name.value)
            .order_by(AgentAction.created_at)
        )
    )


def _last_action(session: Session, name: ToolName) -> AgentAction:
    rows = _actions(session, name)
    assert rows, f"expected at least one {name.value} audit row"
    return rows[-1]


def _reserved(session: Session, variant_id: str) -> int:
    """Currently-reserved qty for a variant (re-queried; survives expire_all)."""
    session.expire_all()
    inv = session.scalar(select(Inventory).where(Inventory.variant_id == variant_id))
    assert inv is not None
    return inv.qty_reserved


def _capture_order_payment(
    session: Session, user_id: str, order_id: str, payment_id: str
) -> None:
    """Confirm the mock payment to ``captured`` so a refund has something to act on."""
    from app.services import orders as order_service

    session.expire_all()  # shared-session: see the flushed pending payment
    order_service.confirm_payment(
        session,
        user_id,
        order_id,
        payment_id=payment_id,
        outcome=PaymentStatus.captured,
        idempotency_key=None,
    )


def _place_captured_order(
    session: Session, owner: User, variant_id: str
) -> tuple[str, str]:
    """Add->draft->capture for ``owner``; return (order_id, payment_id) refund-ready."""
    execute_tool(
        ToolName.add_to_cart,
        {"variant_id": variant_id, "qty": 1},
        session=session,
        user=owner,
    )
    draft = cast(
        DraftOrderOutput,
        execute_tool(
            ToolName.draft_order, {"ship_address": _SHIP}, session=session, user=owner
        ).output,
    )
    order_id = draft.order.id
    payment_id = draft.payment_intent.payment_id
    _capture_order_payment(session, owner.id, order_id, payment_id)
    return order_id, payment_id


# =========================================================================== #
# 1. search — read.                                                           #
# =========================================================================== #
def test_search_success_returns_typed_results(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        res = execute_tool(
            ToolName.search, {"query": "mug", "limit": 5}, session=s, user=user
        )
        out = cast(SearchOutput, res.output)
        assert res.status_code == 200
        assert isinstance(out, SearchOutput)
        assert out.results, "the seed has a mug; search must return at least one hit"
        assert all(r.product.id for r in out.results)
        assert _last_action(s, ToolName.search).outcome == AgentOutcome.applied.value


def test_search_validation_failure_extra_arg(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        with pytest.raises(APIError) as ei:
            execute_tool(
                ToolName.search,
                {"query": "mug", "nope": "smuggled"},  # extra=forbid
                session=s,
                user=user,
            )
        assert ei.value.status_code == 422
        assert ei.value.code is ErrorCode.validation_error
        assert _last_action(s, ToolName.search).outcome == AgentOutcome.refused.value


def test_search_unauthorized_cross_user_still_reads(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """Reads are any-authed: there is no per-user resource here, so a different valid
    identity simply gets results. The executor-level unauth surface for a public read is
    'an identity is required' (enforced upstream at require_user, not in execute_tool) —
    documented in the module docstring. Asserting the read works for a non-owner buyer."""
    with Session(seeded_db.engine) as s:
        other = _user(s, handles, "buyer_secondary")
        res = execute_tool(ToolName.search, {"query": "mug"}, session=s, user=other)
        assert res.status_code == 200


# =========================================================================== #
# 2. productDetails — read.                                                   #
# =========================================================================== #
def test_product_details_success(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        res = execute_tool(
            ToolName.product_details, {"id_or_slug": _MUG_SLUG}, session=s, user=user
        )
        out = cast(ProductDetail, res.output)
        assert res.status_code == 200
        assert out.slug == _MUG_SLUG
        assert out.variants, "product detail must project its variants"


def test_product_details_validation_failure_missing_arg(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        with pytest.raises(APIError) as ei:
            execute_tool(ToolName.product_details, {}, session=s, user=user)
        assert ei.value.code is ErrorCode.validation_error
        assert ei.value.status_code == 422


def test_product_details_unknown_id_is_not_found(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """Domain rejection: a well-formed id that resolves to nothing -> not_found."""
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        with pytest.raises(APIError) as ei:
            execute_tool(
                ToolName.product_details, {"id_or_slug": _GHOST_UUID}, session=s, user=user
            )
        assert ei.value.code is ErrorCode.not_found
        assert _last_action(s, ToolName.product_details).outcome == (
            AgentOutcome.refused.value
        )


# =========================================================================== #
# 3. inventory — read.                                                        #
# =========================================================================== #
def test_inventory_success_per_variant(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        res = execute_tool(
            ToolName.inventory, {"product_id_or_slug": _MUG_SLUG}, session=s, user=user
        )
        out = cast(InventoryOutput, res.output)
        assert res.status_code == 200
        # mug_in_stock (qty 24) makes the product overall in-stock.
        assert out.any_in_stock is True
        assert out.variants and all(v.sku for v in out.variants)


def test_inventory_validation_failure_extra_field(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        with pytest.raises(APIError) as ei:
            execute_tool(
                ToolName.inventory,
                {"product_id_or_slug": _MUG_SLUG, "qty": 3},  # not a field -> forbid
                session=s,
                user=user,
            )
        assert ei.value.code is ErrorCode.validation_error


def test_inventory_unknown_variant_is_not_found(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """Domain rejection: a real product but a variant_id that isn't its -> not_found."""
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        with pytest.raises(APIError) as ei:
            execute_tool(
                ToolName.inventory,
                {"product_id_or_slug": _MUG_SLUG, "variant_id": _GHOST_UUID},
                session=s,
                user=user,
            )
        assert ei.value.code is ErrorCode.not_found


# =========================================================================== #
# 4. orderStatus — read (owner-scoped).                                       #
# =========================================================================== #
def test_order_status_success(seeded_db: SeededDb, handles: ResolvedHandles) -> None:
    with Session(seeded_db.engine) as s:
        owner = _user(s, handles, "buyer_primary")
        variant = handles.variant_ids["mug_in_stock"]
        execute_tool(
            ToolName.add_to_cart, {"variant_id": variant, "qty": 1}, session=s, user=owner
        )
        draft = cast(
            DraftOrderOutput,
            execute_tool(
                ToolName.draft_order, {"ship_address": _SHIP}, session=s, user=owner
            ).output,
        )
        res = execute_tool(
            ToolName.order_status, {"order_id": draft.order.id}, session=s, user=owner
        )
        out = cast(OrderDetail, res.output)
        assert res.status_code == 200
        assert out.id == draft.order.id
        assert out.status == "placed"


def test_order_status_validation_failure(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        with pytest.raises(APIError) as ei:
            execute_tool(ToolName.order_status, {"order_id": ""}, session=s, user=user)
        assert ei.value.code is ErrorCode.validation_error


def test_order_status_cross_user_is_not_found_no_leak(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """Unauthorized: a different buyer asking for the owner's order -> not_found."""
    with Session(seeded_db.engine) as s:
        owner = _user(s, handles, "buyer_primary")
        other = _user(s, handles, "buyer_secondary")
        variant = handles.variant_ids["mug_in_stock"]
        execute_tool(
            ToolName.add_to_cart, {"variant_id": variant, "qty": 1}, session=s, user=owner
        )
        draft = cast(
            DraftOrderOutput,
            execute_tool(
                ToolName.draft_order, {"ship_address": _SHIP}, session=s, user=owner
            ).output,
        )
        with pytest.raises(APIError) as ei:
            execute_tool(
                ToolName.order_status,
                {"order_id": draft.order.id},
                session=s,
                user=other,
            )
        assert ei.value.code is ErrorCode.not_found
        assert _last_action(s, ToolName.order_status).outcome == (
            AgentOutcome.refused.value
        )


# =========================================================================== #
# 5. addToCart — mutating.                                                    #
# =========================================================================== #
def test_add_to_cart_success_line_present(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        variant = handles.variant_ids["mug_in_stock"]
        res = execute_tool(
            ToolName.add_to_cart, {"variant_id": variant, "qty": 2}, session=s, user=user
        )
        out = cast(CartOut, res.output)
        assert res.status_code == 201
        assert out.item_count == 2
        # Real effect: the line is present for this variant.
        line = next((it for it in out.items if it.variant_id == variant), None)
        assert line is not None and line.qty == 2
        assert _last_action(s, ToolName.add_to_cart).outcome == AgentOutcome.applied.value


def test_add_to_cart_validation_failure_qty_zero(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        variant = handles.variant_ids["mug_in_stock"]
        with pytest.raises(APIError) as ei:
            execute_tool(
                ToolName.add_to_cart,
                {"variant_id": variant, "qty": 0},  # ge=1
                session=s,
                user=user,
            )
        assert ei.value.code is ErrorCode.validation_error


def test_add_to_cart_over_availability_is_out_of_stock(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """Domain rejection: an out-of-stock variant -> out_of_stock (409), audited refused."""
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        oos = handles.variant_ids["wallet_oos"]  # qty_on_hand 0
        with pytest.raises(APIError) as ei:
            execute_tool(
                ToolName.add_to_cart, {"variant_id": oos, "qty": 1}, session=s, user=user
            )
        assert ei.value.status_code == 409
        assert ei.value.code is ErrorCode.out_of_stock
        assert _last_action(s, ToolName.add_to_cart).outcome == (
            AgentOutcome.refused.value
        )


def test_add_to_cart_unknown_variant_is_not_found(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """Unauthorized/non-existent resource: a ghost variant id -> not_found (no leak)."""
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        with pytest.raises(APIError) as ei:
            execute_tool(
                ToolName.add_to_cart,
                {"variant_id": _GHOST_UUID, "qty": 1},
                session=s,
                user=user,
            )
        assert ei.value.code is ErrorCode.not_found


# =========================================================================== #
# 6. applyCoupon — pure / deterministic.                                      #
# =========================================================================== #
def test_apply_coupon_welcome10_discounts(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        res = execute_tool(
            ToolName.apply_coupon,
            {"code": "welcome10", "subtotal_minor": 5000},  # case-insensitive match
            session=s,
            user=user,
        )
        out = cast(CouponDiscountOut, res.output)
        assert res.status_code == 200
        assert out.code == "WELCOME10"
        assert out.kind == "percent"
        assert out.discount_minor == 500  # 10% of 5000
        assert _last_action(s, ToolName.apply_coupon).outcome == (
            AgentOutcome.applied.value
        )


def test_apply_coupon_validation_failure_negative_subtotal(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        with pytest.raises(APIError) as ei:
            execute_tool(
                ToolName.apply_coupon,
                {"code": "WELCOME10", "subtotal_minor": -1},  # ge=0
                session=s,
                user=user,
            )
        assert ei.value.code is ErrorCode.validation_error


def test_apply_coupon_unknown_code_is_not_found(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """Domain rejection: an unknown coupon code -> not_found, audited refused."""
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        with pytest.raises(APIError) as ei:
            execute_tool(
                ToolName.apply_coupon,
                {"code": "NOPE-NOT-REAL", "subtotal_minor": 5000},
                session=s,
                user=user,
            )
        assert ei.value.code is ErrorCode.not_found
        assert _last_action(s, ToolName.apply_coupon).outcome == (
            AgentOutcome.refused.value
        )


# =========================================================================== #
# 7. draftOrder — mutating, idempotent.                                       #
# =========================================================================== #
def test_draft_order_success_places_order_intent_and_reserves_stock(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        variant = handles.variant_ids["mug_in_stock"]
        before = _reserved(s, variant)
        execute_tool(
            ToolName.add_to_cart, {"variant_id": variant, "qty": 2}, session=s, user=user
        )
        res = execute_tool(
            ToolName.draft_order, {"ship_address": _SHIP}, session=s, user=user
        )
        draft = cast(DraftOrderOutput, res.output)
        assert res.status_code == 201
        # placed (unpaid) order + a pending payment intent.
        assert draft.order.status == "placed"
        assert draft.payment_intent.status == PaymentStatus.pending
        assert draft.payment_intent.payment_id
        # Real effect: stock reserved by the checkout (qty 2).
        assert _reserved(s, variant) == before + 2
        assert _last_action(s, ToolName.draft_order).outcome == (
            AgentOutcome.applied.value
        )


def test_draft_order_validation_failure_missing_ship_address(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        with pytest.raises(APIError) as ei:
            execute_tool(ToolName.draft_order, {}, session=s, user=user)
        assert ei.value.code is ErrorCode.validation_error


def test_draft_order_empty_cart_is_rejected(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """Domain rejection: checkout with no open cart is a definitive ``empty_cart`` (409).

    Pins to the closed code the order service raises (not prose). buyer_secondary has no
    open cart in a fresh seed, so checkout has nothing to place."""
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_secondary")
        with pytest.raises(APIError) as ei:
            execute_tool(
                ToolName.draft_order, {"ship_address": _SHIP}, session=s, user=user
            )
        assert ei.value.status_code == 409
        assert ei.value.code is ErrorCode.empty_cart
        assert _last_action(s, ToolName.draft_order).outcome == (
            AgentOutcome.refused.value
        )


# =========================================================================== #
# 8. refund — mutating, sensitive.                                            #
# =========================================================================== #
def test_refund_success_owner_marks_payment_refunded(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        owner = _user(s, handles, "buyer_primary")
        variant = handles.variant_ids["mug_in_stock"]
        order_id, payment_id = _place_captured_order(s, owner, variant)
        res = execute_tool(
            ToolName.refund,
            {"order_id": order_id, "reason": "changed mind"},
            session=s,
            user=owner,
        )
        out = cast(RefundOutput, res.output)
        assert res.status_code == 200
        assert out.payment.status == PaymentStatus.refunded
        # Real effect: the captured Payment row is now refunded.
        s.expire_all()
        pay = s.get(Payment, payment_id)
        assert pay is not None and pay.status == PaymentStatus.refunded.value
        assert _last_action(s, ToolName.refund).outcome == AgentOutcome.applied.value


def test_refund_success_privileged_support_any_order(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """Sensitive scope: a support user may refund an order they do NOT own."""
    with Session(seeded_db.engine) as s:
        owner = _user(s, handles, "buyer_primary")
        support = _user(s, handles, "support")
        variant = handles.variant_ids["mug_in_stock"]
        order_id, payment_id = _place_captured_order(s, owner, variant)
        res = execute_tool(
            ToolName.refund, {"order_id": order_id}, session=s, user=support
        )
        assert cast(RefundOutput, res.output).payment.status == PaymentStatus.refunded
        s.expire_all()
        assert s.get(Payment, payment_id).status == PaymentStatus.refunded.value  # type: ignore[union-attr]


def test_refund_validation_failure_extra_arg(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        with pytest.raises(APIError) as ei:
            execute_tool(
                ToolName.refund,
                {"order_id": _GHOST_UUID, "amount": 100},  # not a field -> forbid
                session=s,
                user=user,
            )
        assert ei.value.code is ErrorCode.validation_error


def test_refund_no_captured_payment_is_conflict(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """Domain rejection: a placed-but-unpaid order has nothing to refund -> 409."""
    with Session(seeded_db.engine) as s:
        owner = _user(s, handles, "buyer_primary")
        variant = handles.variant_ids["mug_in_stock"]
        execute_tool(
            ToolName.add_to_cart, {"variant_id": variant, "qty": 1}, session=s, user=owner
        )
        draft = cast(
            DraftOrderOutput,
            execute_tool(
                ToolName.draft_order, {"ship_address": _SHIP}, session=s, user=owner
            ).output,
        )
        with pytest.raises(APIError) as ei:
            execute_tool(
                ToolName.refund, {"order_id": draft.order.id}, session=s, user=owner
            )
        assert ei.value.status_code == 409
        assert ei.value.code is ErrorCode.conflict


def test_refund_foreign_buyer_is_not_found_no_leak(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """Unauthorized: an ordinary buyer refunding another buyer's order -> not_found."""
    with Session(seeded_db.engine) as s:
        owner = _user(s, handles, "buyer_primary")
        other = _user(s, handles, "buyer_secondary")
        variant = handles.variant_ids["mug_in_stock"]
        order_id, payment_id = _place_captured_order(s, owner, variant)
        with pytest.raises(APIError) as ei:
            execute_tool(ToolName.refund, {"order_id": order_id}, session=s, user=other)
        assert ei.value.code is ErrorCode.not_found
        # No effect: the captured payment is untouched (not refunded by the failed call).
        s.expire_all()
        assert s.get(Payment, payment_id).status == PaymentStatus.captured.value  # type: ignore[union-attr]
        assert _last_action(s, ToolName.refund).outcome == AgentOutcome.refused.value


def test_refund_seller_non_owner_non_support_is_not_found(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """Unauthorized: a seller (non-owner, non-privileged) refunding a buyer's order.

    Per ADR-0029 §3 + the dormant ``_check_scope`` gate, this surfaces as ``not_found``
    (no-leak), NOT ``403 forbidden`` — there is no blanket role gate today. Asserted AS
    BUILT; the 403 seam is noted in the module docstring for the guardrail decision."""
    with Session(seeded_db.engine) as s:
        owner = _user(s, handles, "buyer_primary")
        seller = _user(s, handles, "seller_ceramics")
        variant = handles.variant_ids["mug_in_stock"]
        order_id, _ = _place_captured_order(s, owner, variant)
        with pytest.raises(APIError) as ei:
            execute_tool(ToolName.refund, {"order_id": order_id}, session=s, user=seller)
        assert ei.value.code is ErrorCode.not_found
        assert ei.value.status_code == 404


# =========================================================================== #
# Cross-cutting: idempotency (effect applied once).                           #
# =========================================================================== #
def test_idempotency_add_to_cart_same_key_applies_once(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """Two addToCart calls with the SAME key -> same result, one increment only."""
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        variant = handles.variant_ids["mug_in_stock"]
        before = _reserved(s, variant)  # baseline reservation before any add
        first = execute_tool(
            ToolName.add_to_cart,
            {"variant_id": variant, "qty": 2},
            session=s,
            user=user,
            idempotency_key="k-cart",
        )
        again = execute_tool(
            ToolName.add_to_cart,
            {"variant_id": variant, "qty": 2},
            session=s,
            user=user,
            idempotency_key="k-cart",
        )
        assert first.replayed is False
        assert again.replayed is True
        # Effect applied ONCE: qty is 2, not 4 (the replay didn't re-increment).
        assert cast(CartOut, again.output).item_count == 2
        # addToCart does NOT reserve inventory (reservation is taken at checkout), so the
        # variant's reserved count is unchanged regardless of the replay.
        assert _reserved(s, variant) == before


def test_idempotency_different_key_is_independent(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """A DIFFERENT key (or no key) is an independent call -> the effect re-applies."""
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        variant = handles.variant_ids["mug_in_stock"]
        execute_tool(
            ToolName.add_to_cart,
            {"variant_id": variant, "qty": 2},
            session=s,
            user=user,
            idempotency_key="k-a",
        )
        second = execute_tool(
            ToolName.add_to_cart,
            {"variant_id": variant, "qty": 3},
            session=s,
            user=user,
            idempotency_key="k-b",  # different key -> independent increment
        )
        assert second.replayed is False
        assert cast(CartOut, second.output).item_count == 5  # 2 + 3


def test_idempotency_refund_same_key_refunds_once(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """A retried/replayed refund with the same key does NOT double-refund."""
    with Session(seeded_db.engine) as s:
        owner = _user(s, handles, "buyer_primary")
        variant = handles.variant_ids["mug_in_stock"]
        order_id, payment_id = _place_captured_order(s, owner, variant)
        first = execute_tool(
            ToolName.refund,
            {"order_id": order_id},
            session=s,
            user=owner,
            idempotency_key="k-refund",
        )
        again = execute_tool(
            ToolName.refund,
            {"order_id": order_id},
            session=s,
            user=owner,
            idempotency_key="k-refund",
        )
        assert first.replayed is False
        assert again.replayed is True
        assert cast(RefundOutput, again.output).payment.status == PaymentStatus.refunded
        # Effect once: the payment is refunded, and the replay didn't re-run the mark.
        s.expire_all()
        assert s.get(Payment, payment_id).status == PaymentStatus.refunded.value  # type: ignore[union-attr]


# =========================================================================== #
# Cross-cutting: retry / timeout INSIDE execute_tool (not just the helper).   #
# =========================================================================== #
def test_execute_tool_retries_transient_then_succeeds(
    seeded_db: SeededDb, handles: ResolvedHandles, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A transient pre-effect fault on a read is retried up to the cap, then succeeds.

    Drives the retry path THROUGH ``execute_tool`` (Echo's tests drive ``_run_with_retry``
    in isolation) with an injected zero clock so no wall-time elapses."""
    from app.services import search as search_service

    real_search = search_service.search_products
    calls = {"n": 0}

    def _flaky(*args: object, **kwargs: object) -> object:
        calls["n"] += 1
        if calls["n"] < 2:
            raise TransientToolError("transient retriever blip")
        return real_search(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(search_service, "search_products", _flaky)
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        res = execute_tool(
            ToolName.search,
            {"query": "mug"},
            session=s,
            user=user,
            retry=RetryPolicy(max_attempts=3, timeout_s=100.0, backoff_s=0.0),
            clock=lambda: 0.0,
            sleep=lambda _: None,
        )
        assert isinstance(res, ToolResult)
        assert res.status_code == 200
        assert calls["n"] == 2  # one transient, then success


def test_execute_tool_transient_exhaustion_is_rate_limited(
    seeded_db: SeededDb, handles: ResolvedHandles, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exhausting all attempts on a transient fault surfaces rate_limited (429)."""
    from app.services import search as search_service

    calls = {"n": 0}

    def _always_transient(*args: object, **kwargs: object) -> object:
        calls["n"] += 1
        raise TransientToolError("never settles")

    monkeypatch.setattr(search_service, "search_products", _always_transient)
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        with pytest.raises(APIError) as ei:
            execute_tool(
                ToolName.search,
                {"query": "mug"},
                session=s,
                user=user,
                retry=RetryPolicy(max_attempts=3, timeout_s=100.0, backoff_s=0.0),
                clock=lambda: 0.0,
                sleep=lambda _: None,
            )
        assert ei.value.status_code == 429
        assert ei.value.code is ErrorCode.rate_limited
        assert calls["n"] == 3  # cap honored
        assert _last_action(s, ToolName.search).outcome == AgentOutcome.refused.value


def test_execute_tool_domain_error_not_retried(
    seeded_db: SeededDb, handles: ResolvedHandles, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A domain APIError raised by the service is definitive — executed exactly once."""
    from app.services import search as search_service

    calls = {"n": 0}

    def _refuses(*args: object, **kwargs: object) -> object:
        calls["n"] += 1
        raise APIError(404, ErrorCode.not_found, "gone")

    monkeypatch.setattr(search_service, "search_products", _refuses)
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        with pytest.raises(APIError) as ei:
            execute_tool(
                ToolName.search,
                {"query": "mug"},
                session=s,
                user=user,
                retry=RetryPolicy(max_attempts=3, timeout_s=100.0, backoff_s=0.0),
                clock=lambda: 0.0,
                sleep=lambda _: None,
            )
        assert ei.value.code is ErrorCode.not_found
        assert calls["n"] == 1  # never retried


def test_retried_mutating_call_does_not_double_apply(
    seeded_db: SeededDb, handles: ResolvedHandles, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mutating tool that transiently fails BEFORE committing, then succeeds on retry
    under one idempotency key, applies its effect exactly once (no double reserve).

    The transient fault is raised pre-effect (the safe-by-construction rule), so the
    successful attempt is the only one that commits; the idempotency window guards any
    later replay."""
    from app.services import cart as cart_service

    real_add = cart_service.add_item
    calls = {"n": 0}

    def _flaky_add(*args: object, **kwargs: object) -> object:
        calls["n"] += 1
        if calls["n"] < 2:
            raise TransientToolError("pre-effect blip")  # before any DB write
        return real_add(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(cart_service, "add_item", _flaky_add)
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        variant = handles.variant_ids["mug_in_stock"]
        res = execute_tool(
            ToolName.add_to_cart,
            {"variant_id": variant, "qty": 2},
            session=s,
            user=user,
            idempotency_key="k-flaky",
            retry=RetryPolicy(max_attempts=3, timeout_s=100.0, backoff_s=0.0),
            clock=lambda: 0.0,
            sleep=lambda _: None,
        )
        assert calls["n"] == 2  # one transient, then the committing attempt
        # Effect applied exactly once: qty 2, not 4.
        assert cast(CartOut, res.output).item_count == 2


# =========================================================================== #
# Cross-cutting: audit row per terminal call (applied vs refused).            #
# =========================================================================== #
def test_audit_outcome_applied_on_success_refused_on_rejection(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """One AgentAction per terminal call, with the right action_type + outcome."""
    with Session(seeded_db.engine) as s:
        user = _user(s, handles, "buyer_primary")
        # applied
        execute_tool(
            ToolName.apply_coupon,
            {"code": "WELCOME10", "subtotal_minor": 1000},
            session=s,
            user=user,
        )
        # refused (unknown code)
        with pytest.raises(APIError):
            execute_tool(
                ToolName.apply_coupon,
                {"code": "GHOST", "subtotal_minor": 1000},
                session=s,
                user=user,
            )
        rows = _actions(s, ToolName.apply_coupon)
        assert len(rows) == 2
        assert rows[0].action_type == ToolName.apply_coupon.value
        assert rows[0].outcome == AgentOutcome.applied.value
        assert rows[1].outcome == AgentOutcome.refused.value
        assert all(r.actor_user_id == user.id for r in rows)
