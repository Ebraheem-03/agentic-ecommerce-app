"""Tool execution layer — validate, scope, idempotency, retry, audit (US-E5-02, ADR-0029).

ONE dispatcher, ``execute_tool``, sits between the (later) agent loop and the domain
services. For every tool call it:

  1. VALIDATES ``raw_args`` against the tool's input model -> ``APIError(422,
     validation_error)`` with per-field details (never a bare HTTPException).
  2. CHECKS AUTH SCOPE per tool (ADR-0029 policy):
       * reads (search / productDetails / inventory / orderStatus) — any authed user;
       * addToCart / draftOrder — the acting buyer/owner (their own cart/order);
       * refund — SENSITIVE — order owner OR a support/admin role.
     There is ONE identity path for humans and agents: the caller passes the ``User``
     resolved by ``require_user`` / ``require_role`` (``app.api.deps``). Wrong scope ->
     ``APIError(403, forbidden)``; cross-user resource access surfaces as ``not_found``
     (no existence leak), matching the HTTP handlers.
  3. EXECUTES against the real service function (NOT over HTTP).
  4. IDEMPOTENCY for mutating tools (addToCart / draftOrder / refund) via
     ``app.services.idempotency`` with ``endpoint=f"tool:{name}"``. A replay re-emits the
     stored result, re-raising a stored error status where relevant. No-op without a key.
  5. TIMEOUT + BOUNDED RETRY around execution (injectable clock/runner so QA can drive
     it). See the retry policy block below.
  6. AUDIT: every call writes an ``AgentAction`` row (action_type=name, payload, outcome
     ∈ applied | refused | hitl_deferred; conversation_id may be None for tool-only calls).

RETRY POLICY (ADR-0029)
=======================
Retries are SAFE-BY-CONSTRUCTION, not best-effort:
  * Retries only ever wrap the service call, and a retryable failure is one raised BEFORE
    any committed side effect (modeled as ``TransientToolError``). A domain ``APIError``
    (validation/forbidden/not_found/out_of_stock/...) is a definitive answer and is NEVER
    retried — re-running it just repeats the same refusal.
  * For mutating tools the retry runs INSIDE the idempotency guard window: the first
    attempt that commits stores its result, so a later attempt/replay re-emits it rather
    than double-applying. Combined with the pre-effect rule, no non-idempotent work is
    ever retried unsafely.
  * Exhaustion (all ``max_attempts`` failed) or a per-attempt timeout overrun ->
    ``APIError(429, rate_limited)`` (a clean, closed-code envelope; chosen over 500 so the
    caller/agent can back off and retry the whole turn).

The retry/timeout machinery is parameterized (``RetryPolicy`` + an injectable ``clock``)
so US-QA-D12 can drive exhaustion, timeout, and replay deterministically without sleeps.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.agent.tools import (
    REGISTRY,
    AddToCartInput,
    ApplyCouponInput,
    CouponDiscountOut,
    DraftOrderInput,
    DraftOrderOutput,
    InventoryInput,
    InventoryOutput,
    OrderStatusInput,
    ProductDetailsInput,
    RefundInput,
    RefundOutput,
    ScoredProductOut,
    SearchInput,
    SearchOutput,
    ToolName,
    VariantStockOut,
)
from app.core.errors import APIError
from app.db.models import AgentAction, Order, User
from app.schemas.cart import CartOut
from app.schemas.enums import AgentOutcome, PaymentStatus, UserRole
from app.schemas.envelope import ErrorCode
from app.schemas.order import PaymentIntentOut
from app.services import cart as cart_service
from app.services import catalog as catalog_service
from app.services import coupons as coupon_service
from app.services import idempotency as idempotency_service
from app.services import orders as order_service
from app.services import search as search_service

# Roles allowed to invoke the sensitive ``refund`` tool on an order they do NOT own.
_PRIVILEGED_ROLES = {UserRole.support.value, UserRole.admin.value}


# --------------------------------------------------------------------------- #
# Retry / timeout policy.                                                       #
# --------------------------------------------------------------------------- #
class TransientToolError(Exception):
    """A retryable failure raised BEFORE any committed side effect.

    Service code (or a test) raises this to signal "safe to retry" — e.g. a transient
    pre-effect fault. A domain ``APIError`` is NOT this and is never retried.
    """


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded-retry + per-attempt timeout knobs (injectable for deterministic tests)."""

    max_attempts: int = 3
    timeout_s: float = 10.0
    backoff_s: float = 0.0  # 0 by default so tests don't sleep


DEFAULT_RETRY = RetryPolicy()


def _rate_limited(msg: str) -> APIError:
    return APIError(status_code=429, code=ErrorCode.rate_limited, message=msg)


def _run_with_retry(
    fn: Callable[[], Any],
    *,
    policy: RetryPolicy,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
) -> Any:
    """Run ``fn`` with bounded retry on ``TransientToolError`` + a per-attempt timeout.

    A ``TransientToolError`` (pre-effect, retryable) is retried up to ``max_attempts``;
    exhaustion -> ``rate_limited`` (429). Any ``APIError`` is a definitive answer and is
    re-raised immediately (never retried). A per-attempt overrun of ``timeout_s`` (wall
    time around the call) also surfaces as ``rate_limited``.
    """
    last: TransientToolError | None = None
    for attempt in range(1, policy.max_attempts + 1):
        started = clock()
        try:
            result = fn()
        except APIError:
            raise  # definitive — do not retry a domain refusal
        except TransientToolError as exc:
            last = exc
            if clock() - started > policy.timeout_s:
                raise _rate_limited("That took too long — please try again.") from exc
            if attempt < policy.max_attempts and policy.backoff_s:
                sleep(policy.backoff_s)
            continue
        if clock() - started > policy.timeout_s:
            raise _rate_limited("That took too long — please try again.")
        return result
    raise _rate_limited("That request kept failing — please try again.") from last


# --------------------------------------------------------------------------- #
# Result envelope.                                                              #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class ToolResult:
    """The outcome of a tool call: a typed output, a status, and whether it replayed."""

    name: ToolName
    output: BaseModel
    status_code: int
    replayed: bool = False


# --------------------------------------------------------------------------- #
# Scope helpers — refunds are the only privileged tool; everything else is      #
# either any-authed (reads) or owner-scoped via the service's own 404-on-foreign.#
# --------------------------------------------------------------------------- #
def _forbidden() -> APIError:
    return APIError(
        status_code=403,
        code=ErrorCode.forbidden,
        message="You don't have access to that.",
    )


def _not_found(thing: str) -> APIError:
    return APIError(
        status_code=404,
        code=ErrorCode.not_found,
        message=f"We couldn't find that {thing}.",
    )


# --------------------------------------------------------------------------- #
# Per-tool execution. Each returns (output_model, status_code). Owner-scoping    #
# for cart/order tools is delegated to the services (they 404 on foreign rows).  #
# --------------------------------------------------------------------------- #
def _exec_search(session: Session, user: User, args: SearchInput) -> tuple[BaseModel, int]:
    env = search_service.search_products(
        session, q=args.query, category=args.category, cursor=None, limit=args.limit
    )
    out = SearchOutput(
        results=[
            ScoredProductOut(product=r.product, score=r.score) for r in env.data
        ],
        mode=env.meta.mode,
    )
    return out, 200


def _exec_product_details(
    session: Session, user: User, args: ProductDetailsInput
) -> tuple[BaseModel, int]:
    detail = catalog_service.get_product(session, args.id_or_slug)
    return detail, 200


def _exec_inventory(
    session: Session, user: User, args: InventoryInput
) -> tuple[BaseModel, int]:
    # Reuse product detail (it already projects per-variant stock signals).
    detail = catalog_service.get_product(session, args.product_id_or_slug)
    variants = detail.variants
    if args.variant_id is not None:
        variants = [v for v in variants if v.id == args.variant_id]
        if not variants:
            raise _not_found("variant")
    out = InventoryOutput(
        product_id=detail.id,
        any_in_stock=any(v.in_stock for v in variants),
        variants=[
            VariantStockOut(
                variant_id=v.id,
                sku=v.sku,
                in_stock=v.in_stock,
                restock_eta_days=v.restock_eta_days,
            )
            for v in variants
        ],
    )
    return out, 200


def _exec_add_to_cart(
    session: Session, user: User, args: AddToCartInput
) -> tuple[BaseModel, int]:
    cart = cart_service.add_item(
        session, user.id, variant_id=args.variant_id, qty=args.qty
    )
    return cart, 201


def _exec_apply_coupon(
    session: Session, user: User, args: ApplyCouponInput
) -> tuple[BaseModel, int]:
    discount = coupon_service.validate_coupon(
        args.code, subtotal_minor=args.subtotal_minor, currency=args.currency
    )
    out = CouponDiscountOut(
        code=discount.code,
        kind=discount.kind.value,
        value=discount.value,
        discount_minor=discount.discount_minor,
        currency=discount.currency,
    )
    return out, 200


def _exec_draft_order(
    session: Session, user: User, args: DraftOrderInput
) -> tuple[BaseModel, int]:
    # Plan-execute step: checkout the open cart (places the order), then create the
    # payment intent — WITHOUT confirming payment. Both reuse the order service.
    detail, _ = order_service.checkout(
        session, user.id, ship_address=args.ship_address, idempotency_key=None
    )
    # The agent layer runs both service calls on ONE shared session (unlike the HTTP
    # layer's per-request session). checkout() loaded the Order with an eager (empty)
    # ``payments`` collection; expiring it forces create_payment_intent's reload to see
    # the freshly-inserted payment instead of the stale cached collection.
    session.expire_all()
    intent: PaymentIntentOut
    intent, _ = order_service.create_payment_intent(
        session, user.id, detail.id, idempotency_key=None
    )
    out = DraftOrderOutput(order=detail, payment_intent=intent)
    return out, 201


def _exec_order_status(
    session: Session, user: User, args: OrderStatusInput
) -> tuple[BaseModel, int]:
    detail = order_service.get_order(session, user.id, args.order_id)
    return detail, 200


def _exec_refund(
    session: Session, user: User, args: RefundInput
) -> tuple[BaseModel, int]:
    """Refund the captured payment on an order (v0 thin shim — ADR-0029).

    Scope: the order owner OR a support/admin user. A privileged user may refund any
    order; an ordinary buyer may only refund their own (a foreign order id surfaces as
    ``not_found``, never a leak). Marks the order's captured ``Payment`` -> refunded and
    records the action. The full returns/refund epic (returns router still 501) is later.
    """
    is_privileged = user.role in _PRIVILEGED_ROLES
    order = session.get(Order, args.order_id) if _looks_like_uuid(args.order_id) else None
    if order is None:
        raise _not_found("order")
    if not is_privileged and order.user_id != user.id:
        # Ordinary buyer touching a foreign order — mirror the handlers' no-leak 404.
        raise _not_found("order")

    captured = next(
        (p for p in order.payments if p.status == PaymentStatus.captured.value), None
    )
    if captured is None:
        raise APIError(
            status_code=409,
            code=ErrorCode.conflict,
            message="There's no captured payment to refund on that order.",
        )
    captured.status = PaymentStatus.refunded.value
    session.flush()

    out = RefundOutput(
        order_id=order.id,
        payment=order_service._payment_out(captured),  # noqa: SLF001 — same package intent
    )
    return out, 200


def _looks_like_uuid(value: str) -> bool:
    import uuid

    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


_EXECUTORS: dict[ToolName, Callable[[Session, User, Any], tuple[BaseModel, int]]] = {
    ToolName.search: _exec_search,
    ToolName.product_details: _exec_product_details,
    ToolName.inventory: _exec_inventory,
    ToolName.add_to_cart: _exec_add_to_cart,
    ToolName.apply_coupon: _exec_apply_coupon,
    ToolName.draft_order: _exec_draft_order,
    ToolName.order_status: _exec_order_status,
    ToolName.refund: _exec_refund,
}


# --------------------------------------------------------------------------- #
# Validation.                                                                   #
# --------------------------------------------------------------------------- #
def _validate(name: ToolName, raw_args: dict[str, Any]) -> BaseModel:
    """Parse ``raw_args`` against the tool's input model; 422 with per-field details."""
    model = REGISTRY[name].input_model
    try:
        return model.model_validate(raw_args)
    except ValidationError as exc:
        raise APIError(
            status_code=422,
            code=ErrorCode.validation_error,
            message="Those tool arguments didn't look right.",
            details={"errors": exc.errors(include_url=False)},
        ) from exc


# --------------------------------------------------------------------------- #
# Scope.                                                                        #
# --------------------------------------------------------------------------- #
def _check_scope(name: ToolName, user: User) -> None:
    """Role-class gate. Owner-level scoping is enforced inside the services (404 on
    foreign rows) and, for refund, inside ``_exec_refund``; this gate only blocks the
    role-class case there is one of — the sensitive ``refund`` tool needs no extra role
    by default (owner is allowed), so the gate is a no-op today but is the single seam
    where a stricter "refund requires support/admin always" policy would land."""
    # No tool requires a blanket role today: reads + buyer-mutations are any-authed, and
    # refund permits the owner. The sensitive flag drives ownership logic in _exec_refund.
    _ = (name, user)


# --------------------------------------------------------------------------- #
# Audit.                                                                        #
# --------------------------------------------------------------------------- #
def _audit(
    session: Session,
    *,
    name: ToolName,
    user: User,
    conversation_id: str | None,
    outcome: AgentOutcome,
    payload: dict[str, Any],
) -> None:
    """Record one tool execution as an ``agent_actions`` row (best-effort, same txn)."""
    session.add(
        AgentAction(
            conversation_id=conversation_id,
            actor_user_id=user.id,
            action_type=name.value,
            payload=payload,
            outcome=outcome.value,
        )
    )
    session.flush()


def _audit_payload(args: BaseModel, status_code: int, *, replayed: bool) -> dict[str, Any]:
    return {
        "args": args.model_dump(mode="json"),
        "status_code": status_code,
        "replayed": replayed,
    }


# --------------------------------------------------------------------------- #
# The dispatcher.                                                               #
# --------------------------------------------------------------------------- #
def execute_tool(
    name: ToolName | str,
    raw_args: dict[str, Any],
    *,
    session: Session,
    user: User,
    conversation_id: str | None = None,
    idempotency_key: str | None = None,
    retry: RetryPolicy = DEFAULT_RETRY,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> ToolResult:
    """Validate, scope, (idempotently) execute, retry, and audit one tool call.

    ``name`` may be a ``ToolName`` or its string value. ``user`` is the identity resolved
    the SAME way as HTTP handlers (``require_user``/``require_role``). ``idempotency_key``
    is honored only for mutating tools. ``retry``/``clock``/``sleep`` are injectable so
    QA can drive retry/timeout deterministically (US-QA-D12).

    Raises ``APIError`` (closed code, canonical envelope) on any failure — validation,
    scope, domain refusal, or retry exhaustion. Every terminal path writes an audit row.
    """
    name = ToolName(name)
    spec = REGISTRY[name]

    # 1. Validate. A validation failure is audited as a refusal then re-raised.
    try:
        args = _validate(name, raw_args)
    except APIError:
        _audit(
            session,
            name=name,
            user=user,
            conversation_id=conversation_id,
            outcome=AgentOutcome.refused,
            payload={"raw_args": raw_args, "reason": "validation_error"},
        )
        raise

    # 2. Scope (role-class gate; owner scoping lives in the services / _exec_refund).
    try:
        _check_scope(name, user)
    except APIError:
        _audit(
            session,
            name=name,
            user=user,
            conversation_id=conversation_id,
            outcome=AgentOutcome.refused,
            payload={"args": args.model_dump(mode="json"), "reason": "forbidden"},
        )
        raise

    endpoint = f"tool:{name.value}"

    # 3/4. Mutating tools: idempotency replay first.
    if spec.mutating and idempotency_key:
        replay = idempotency_service.lookup(session, user.id, idempotency_key, endpoint)
        if replay is not None:
            return _replay_result(
                session,
                name=name,
                user=user,
                conversation_id=conversation_id,
                args=args,
                replay=replay,
            )

    # The agent layer runs many tool calls on ONE long-lived session (unlike the HTTP
    # layer's fresh per-request session). Expire cached ORM state before each execution
    # so a tool sees committed/flushed effects from earlier tool calls — e.g. a payment
    # created by draftOrder is visible to a later refund/orderStatus — rather than a
    # stale identity-mapped collection. Reads are unaffected; this just drops the cache.
    session.expire_all()

    # 5. Execute under the retry/timeout wrapper. Reads + pure tools may retry on a
    # transient pre-effect fault; mutating tools retry inside the idempotency window.
    executor = _EXECUTORS[name]

    def _call() -> tuple[BaseModel, int]:
        return executor(session, user, args)

    try:
        output, status_code = _run_with_retry(
            _call, policy=retry, clock=clock, sleep=sleep
        )
    except APIError as exc:
        # A domain refusal (or retry exhaustion). Audit + store under the idempotency key
        # so a replay re-raises the same status rather than re-running effects.
        if spec.mutating and idempotency_key:
            idempotency_service.store(
                session,
                user.id,
                idempotency_key,
                endpoint,
                status_code=exc.status_code,
                body={"error": {"code": exc.code.value, "message": exc.message}},
            )
        _audit(
            session,
            name=name,
            user=user,
            conversation_id=conversation_id,
            outcome=AgentOutcome.refused,
            payload={
                "args": args.model_dump(mode="json"),
                "error_code": exc.code.value,
                "status_code": exc.status_code,
            },
        )
        raise

    # 4 (store). Memoize the success for mutating tools so a later key replay re-emits it.
    if spec.mutating and idempotency_key:
        idempotency_service.store(
            session,
            user.id,
            idempotency_key,
            endpoint,
            status_code=status_code,
            body=output,
        )

    # 6. Audit the applied outcome.
    _audit(
        session,
        name=name,
        user=user,
        conversation_id=conversation_id,
        outcome=AgentOutcome.applied,
        payload=_audit_payload(args, status_code, replayed=False),
    )
    return ToolResult(name=name, output=output, status_code=status_code)


# --------------------------------------------------------------------------- #
# Replay reconstruction — re-emit a stored mutating-tool result.                #
# --------------------------------------------------------------------------- #
# Each mutating tool's stored success body maps back to its typed output model.
_REPLAY_OUTPUT: dict[ToolName, type[BaseModel]] = {
    ToolName.add_to_cart: CartOut,
    ToolName.draft_order: DraftOrderOutput,
    ToolName.refund: RefundOutput,
}


def _replay_result(
    session: Session,
    *,
    name: ToolName,
    user: User,
    conversation_id: str | None,
    args: BaseModel,
    replay: idempotency_service.StoredResult,
) -> ToolResult:
    """Re-emit a stored mutating-tool result (re-raising a stored error status)."""
    # A stored error body re-raises the same APIError status (e.g. an earlier 409).
    if "error" in replay.body:
        err = replay.body["error"]
        _audit(
            session,
            name=name,
            user=user,
            conversation_id=conversation_id,
            outcome=AgentOutcome.refused,
            payload={"args": args.model_dump(mode="json"), "replayed": True},
        )
        raise APIError(
            status_code=replay.status_code,
            code=ErrorCode(err["code"]),
            message=err["message"],
        )

    model = _REPLAY_OUTPUT[name]
    output = model.model_validate(replay.body)
    _audit(
        session,
        name=name,
        user=user,
        conversation_id=conversation_id,
        outcome=AgentOutcome.applied,
        payload=_audit_payload(args, replay.status_code, replayed=True),
    )
    return ToolResult(
        name=name, output=output, status_code=replay.status_code, replayed=True
    )


__all__ = [
    "DEFAULT_RETRY",
    "RetryPolicy",
    "ToolResult",
    "TransientToolError",
    "execute_tool",
]
