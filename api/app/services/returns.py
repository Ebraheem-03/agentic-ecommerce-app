"""Returns: request, list, get, and the support/admin (or HITL) decision (US-E6/J-SUP-03).

Routers stay thin; the return lifecycle + the within-window policy + the refund reuse
live here. Mirrors ``app.services.orders`` / ``app.services.catalog``.

WITHIN-WINDOW POLICY (v0):
    A return is "within window" if it is requested within ``RETURN_WINDOW_DAYS`` (30)
    of the order's ``placed_at``. The Order/OrderItem models carry no delivered-at
    timestamp (OrderStatus has a ``delivered`` label but no column), so ``placed_at`` is
    the only reliable server-side anchor — chosen deliberately and documented here +
    in ADR-0043. A real delivered-at column can move the anchor later without a contract
    change (``within_window`` is computed, not stored by the client).

DIRECT vs AGENT path (locked contract, ``schemas/returns.py``):
    * DIRECT (non-agent HTTP) request OUTSIDE the window -> ``409 return_window_closed``.
    * AGENT-ASSISTED request outside the window -> create the return in ``hitl_pending``
      for a human to approve/reject (the J-BUY-06 / J-SUP-03 HITL flow).
    The two paths are distinguished by the service-level ``allow_hitl`` flag: the HTTP
    handler passes ``allow_hitl=False`` (the strict direct path); the agent return/refund
    tool can pass ``allow_hitl=True`` to defer out-of-window requests to a human instead
    of hard-failing. In-window requests are identical on both paths (status ``requested``).

DECISION (PATCH /returns/{id}):
    support/admin (or a HITL resolution) moves a return to approved | rejected | refunded.
    On ``refunded`` we reuse the shared payment-refund mutation in ``app.services.orders``
    (``refund_captured_payment``) — NO duplicated payment logic here. ``resolved_at`` +
    ``approved_by`` are stamped on any terminal decision.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.interfaces import LoaderOption

from app.api.pagination import decode_cursor, encode_cursor
from app.core.errors import APIError
from app.db.models import Order, User
from app.db.models.returns import Return, ReturnItem
from app.schemas.enums import ReturnReason, ReturnStatus, UserRole
from app.schemas.envelope import ErrorCode, ListEnvelope, PageMeta
from app.schemas.returns import ReturnCreate, ReturnDecision, ReturnItemOut, ReturnOut
from app.services import orders as orders_service
from app.services.errors import not_found

# v0 return window: 30 days from the order's placed_at. See module docstring + ADR-0043.
RETURN_WINDOW_DAYS = 30

# Roles that can list ALL returns and decide them (the support desk + admin).
_SUPPORT_ROLES = frozenset({UserRole.support.value, UserRole.admin.value})

# Terminal decision targets a PATCH /returns/{id} may set.
_DECIDABLE = frozenset(
    {ReturnStatus.approved, ReturnStatus.rejected, ReturnStatus.refunded}
)


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _return_window_closed() -> APIError:
    return APIError(
        status_code=409,
        code=ErrorCode.return_window_closed,
        message="That order is past its return window.",
    )


def _conflict(message: str) -> APIError:
    return APIError(status_code=409, code=ErrorCode.conflict, message=message)


def _forbidden() -> APIError:
    return APIError(
        status_code=403,
        code=ErrorCode.forbidden,
        message="You don't have access to that.",
    )


def _within_window(order: Order, *, now: datetime) -> bool:
    """True if ``now`` is within ``RETURN_WINDOW_DAYS`` of the order's placed_at."""
    deadline = order.placed_at + timedelta(days=RETURN_WINDOW_DAYS)
    return now <= deadline


def _return_out(ret: Return) -> ReturnOut:
    items = sorted(ret.items, key=lambda it: it.id)
    return ReturnOut(
        id=ret.id,
        order_id=ret.order_id,
        status=ReturnStatus(ret.status),
        reason_code=ReturnReason(ret.reason_code),
        note=ret.note,
        within_window=ret.within_window,
        approved_by=ret.approved_by,
        items=[ReturnItemOut(id=it.id, order_item_id=it.order_item_id, qty=it.qty) for it in items],
        created_at=ret.created_at,
        resolved_at=ret.resolved_at,
    )


def _eager() -> list[LoaderOption]:
    return [selectinload(Return.items)]


def _load_own_order(session: Session, user_id: str, order_id: str) -> Order:
    """The caller's order (eager items) or 404 — never leaks a foreign order."""
    if not _is_uuid(order_id):
        raise not_found("order")
    order = session.scalars(
        select(Order)
        .where(Order.id == order_id, Order.user_id == user_id)
        .options(selectinload(Order.items))
    ).first()
    if order is None:
        raise not_found("order")
    return order


# --------------------------------------------------------------------------- #
# Request a return (nested under POST /orders/{id}/returns).                    #
# --------------------------------------------------------------------------- #
def request_return(
    session: Session,
    user_id: str,
    order_id: str,
    body: ReturnCreate,
    *,
    allow_hitl: bool = False,
) -> tuple[ReturnOut, int]:
    """Create a return for the caller's order. Returns ``(out, status_code)`` (201).

    Within window -> status ``requested``. Outside window: ``allow_hitl=False`` (the
    direct HTTP path) raises ``409 return_window_closed``; ``allow_hitl=True`` (the agent
    path) instead creates the return in ``hitl_pending`` for a human to resolve.
    Items must reference real order_items on THIS order; a foreign/missing order is 404.
    """
    order = _load_own_order(session, user_id, order_id)

    # Validate every requested line references a real order_item on this order.
    valid_ids = {it.id: it for it in order.items}
    seen: set[str] = set()
    for line in body.items:
        if line.order_item_id not in valid_ids:
            raise APIError(
                status_code=422,
                code=ErrorCode.validation_error,
                message="A return line references an item that isn't on this order.",
            )
        if line.order_item_id in seen:
            raise APIError(
                status_code=422,
                code=ErrorCode.validation_error,
                message="A return line is duplicated.",
            )
        seen.add(line.order_item_id)
        order_item = valid_ids[line.order_item_id]
        if line.qty > order_item.qty:
            raise APIError(
                status_code=422,
                code=ErrorCode.validation_error,
                message="A return line asks for more than was ordered.",
            )

    now = datetime.now(UTC)
    within = _within_window(order, now=now)
    if not within and not allow_hitl:
        # Direct path, out of window -> hard 409 (locked contract).
        raise _return_window_closed()

    status_value = ReturnStatus.requested.value
    if not within:
        # Agent path, out of window -> defer to a human.
        status_value = ReturnStatus.hitl_pending.value

    ret = Return(
        order_id=order.id,
        status=status_value,
        reason_code=body.reason_code.value,
        note=body.note,
        within_window=within,
    )
    for line in body.items:
        ret.items.append(ReturnItem(order_item_id=line.order_item_id, qty=line.qty))
    session.add(ret)
    session.flush()
    session.refresh(ret)
    return _return_out(ret), 201


# --------------------------------------------------------------------------- #
# Reads.                                                                        #
# --------------------------------------------------------------------------- #
def list_returns(
    session: Session,
    user: User,
    *,
    status_filter: str | None,
    cursor: str | None,
    limit: int,
) -> ListEnvelope[ReturnOut]:
    """List returns, newest first, cursor-paginated.

    Buyers see only their own returns (joined through the owning order). support/admin
    see ALL returns (incl. ``hitl_pending``) and may filter by ``status``.
    """
    role = getattr(user, "role", UserRole.buyer.value)
    user_id = user.id
    is_support = role in _SUPPORT_ROLES

    stmt = (
        select(Return)
        .options(*_eager())
        .order_by(Return.created_at.desc(), Return.id.desc())
    )
    if not is_support:
        stmt = stmt.join(Order, Return.order_id == Order.id).where(
            Order.user_id == user_id
        )
    if status_filter is not None:
        stmt = stmt.where(Return.status == status_filter)
    if cursor is not None:
        pos = decode_cursor(cursor)
        stmt = stmt.where(
            (Return.created_at < pos.created_at)
            | ((Return.created_at == pos.created_at) & (Return.id < pos.id))
        )

    rows = list(session.scalars(stmt.limit(limit + 1)))
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = (
        encode_cursor(page[-1].created_at, page[-1].id) if has_more and page else None
    )
    return ListEnvelope(
        data=[_return_out(r) for r in page],
        meta=PageMeta(next_cursor=next_cursor, limit=limit, total=None),
    )


def _load_visible_return(session: Session, user: User, return_id: str) -> Return:
    """A return the caller may see (owner OR support/admin) or 404 — no leak."""
    if not _is_uuid(return_id):
        raise not_found("return")
    ret = session.scalars(
        select(Return).where(Return.id == return_id).options(*_eager())
    ).first()
    if ret is None:
        raise not_found("return")

    role = getattr(user, "role", UserRole.buyer.value)
    if role in _SUPPORT_ROLES:
        return ret

    user_id = user.id
    owner_id = session.scalar(select(Order.user_id).where(Order.id == ret.order_id))
    if owner_id != user_id:
        # No-leak: a foreign return is indistinguishable from a missing one.
        raise not_found("return")
    return ret


def get_return(session: Session, user: User, return_id: str) -> ReturnOut:
    """Single return detail — owner or support/admin (404 no-leak otherwise)."""
    return _return_out(_load_visible_return(session, user, return_id))


# --------------------------------------------------------------------------- #
# Decision (support/admin or HITL resolution).                                  #
# --------------------------------------------------------------------------- #
def decide_return(
    session: Session,
    user: User,
    return_id: str,
    body: ReturnDecision,
) -> ReturnOut:
    """Approve / reject / refund a return. support/admin only (403 otherwise).

    Target status ∈ approved | rejected | refunded. On ``refunded`` we reuse the shared
    payment-refund mutation (``orders_service.refund_captured_payment``) — no duplicated
    payment logic. ``resolved_at`` + ``approved_by`` are stamped on the decision. A return
    that is already in a terminal state (approved/rejected/refunded) -> 409 conflict.
    """
    role = getattr(user, "role", UserRole.buyer.value)
    if role not in _SUPPORT_ROLES:
        raise _forbidden()

    if body.status not in _DECIDABLE:
        raise APIError(
            status_code=422,
            code=ErrorCode.validation_error,
            message="A return decision must be approved, rejected, or refunded.",
        )

    ret = _load_visible_return(session, user, return_id)
    current = ReturnStatus(ret.status)
    if current in _DECIDABLE:
        raise _conflict("That return has already been resolved.")

    if body.status is ReturnStatus.refunded:
        # Reuse the shared payment refund — never duplicate the payment mutation.
        orders_service.refund_captured_payment(session, ret.order_id)

    ret.status = body.status.value
    if body.note is not None:
        ret.note = body.note
    ret.approved_by = user.id
    ret.resolved_at = datetime.now(UTC)
    session.flush()
    session.refresh(ret)
    return _return_out(ret)
