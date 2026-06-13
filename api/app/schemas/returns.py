"""Returns: request, list, and the HITL (human-in-the-loop) path.

within-window logic is computed server-side from the order/policy; a request
outside the window yields ``return_window_closed`` (409) on the direct path, but the
agent-assisted path instead creates a return in ``hitl_pending`` for a human to
approve/reject (the J-BUY-06 / J-SUP-03 HITL flow).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.enums import ReturnReason, ReturnStatus
from app.schemas.envelope import CamelModel


class ReturnItemRequest(CamelModel):
    """One line of a return request (references an order item)."""

    order_item_id: str
    qty: int = Field(ge=1, le=999)


class ReturnCreate(CamelModel):
    """POST /orders/{order_id}/returns — request a return."""

    reason_code: ReturnReason
    note: str | None = Field(default=None, max_length=2000)
    items: list[ReturnItemRequest] = Field(min_length=1)


class ReturnItemOut(CamelModel):
    """A persisted return line."""

    id: str
    order_item_id: str
    qty: int = Field(ge=1)


class ReturnOut(CamelModel):
    """A return with status (incl. ``hitl_pending`` for the HITL path)."""

    id: str
    order_id: str
    status: ReturnStatus
    reason_code: ReturnReason
    note: str | None = None
    within_window: bool
    approved_by: str | None = None
    items: list[ReturnItemOut]
    created_at: datetime
    resolved_at: datetime | None = None


class ReturnDecision(CamelModel):
    """PATCH /returns/{id} — support/admin (or HITL) approve/reject/refund."""

    status: ReturnStatus = Field(
        description="Target status: approved | rejected | refunded.",
    )
    note: str | None = Field(default=None, max_length=2000)
