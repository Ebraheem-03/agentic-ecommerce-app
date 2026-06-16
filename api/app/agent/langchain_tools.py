"""LangChain tool adapter — a THIN wrapper over the Week-2 executor (US-E5-04, ADR-0031).

The shopping agent calls the catalog/cart/order domain through the SAME 8 typed tools
the Week-2 layer already validates, scopes, makes idempotent, retries, and audits
(``app.agent.tools`` + ``app.agent.executor``). This module does NOT reimplement any of
that — it builds ``langchain_core.tools.StructuredTool`` objects whose ``func`` is a thin
closure over ``execute_tool``. Each tool:

  * reuses the tool's existing Pydantic input model as the LangChain ``args_schema``
    (so the LLM sees the same strict schema — ``extra="forbid"``),
  * binds the acting ``User`` + the shared ``Session`` + ``conversation_id`` from the
    turn's context (resolved upstream via ``app.api.deps``), and
  * returns the executor's typed output as a JSON-able dict, or a structured error dict
    on an ``APIError`` (the agent sees the failure as data, not an exception).

The acting identity is NEVER taken from the LLM — it is closed over from the request
context. This keeps the one-identity-path invariant (humans and agents resolve through
``require_user``) and means the model can't escalate scope by arguments.

DRAFT-ORDER IS GATED ELSEWHERE. ``draftOrder`` (and any payment step) is NOT exposed as a
freely-callable tool here — the shopping graph routes order placement through an explicit
LangGraph ``interrupt()`` approval stop (see ``graph.py``). The tools surfaced to the
model for autonomous calling are the read + cart-mutation set; the order step is driven by
the graph after human approval.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.tools import StructuredTool
from sqlalchemy.orm import Session

from app.agent.executor import execute_tool
from app.agent.tools import REGISTRY, ToolName
from app.core.errors import APIError
from app.db.models import User

# The tools the shopping agent may call autonomously (discovery + cart). draftOrder /
# refund are intentionally excluded — order placement goes through the graph's approval
# interrupt, and refund belongs to the support agent (Day 16).
SHOPPING_TOOL_NAMES: tuple[ToolName, ...] = (
    ToolName.search,
    ToolName.product_details,
    ToolName.inventory,
    ToolName.add_to_cart,
    ToolName.apply_coupon,
)


def _make_tool_func(
    name: ToolName, *, session: Session, user: User, conversation_id: str | None
) -> Callable[..., dict[str, Any]]:
    """Build the closure LangChain calls for one tool.

    The closure receives validated kwargs from LangChain (against ``args_schema``),
    hands them to ``execute_tool`` (which re-validates + scopes + audits), and returns a
    JSON-able dict. An ``APIError`` is caught and returned as a structured error payload
    so the model can react to a refusal instead of the graph crashing.
    """

    def _call(**kwargs: Any) -> dict[str, Any]:
        try:
            result = execute_tool(
                name,
                kwargs,
                session=session,
                user=user,
                conversation_id=conversation_id,
            )
        except APIError as exc:
            return {
                "ok": False,
                "error": {"code": exc.code.value, "message": exc.message},
            }
        return {
            "ok": True,
            "status": result.status_code,
            "result": result.output.model_dump(mode="json"),
        }

    return _call


def build_shopping_tools(
    *, session: Session, user: User, conversation_id: str | None = None
) -> list[StructuredTool]:
    """Build the LangChain tools the shopping agent may call for THIS turn.

    Identity/session/conversation are closed over from the request context — never
    supplied by the model. Returns a fresh list per turn (the closures capture the
    turn's session), so it must be rebuilt each turn, not cached across turns.
    """
    tools: list[StructuredTool] = []
    for name in SHOPPING_TOOL_NAMES:
        spec = REGISTRY[name]
        tools.append(
            StructuredTool.from_function(
                func=_make_tool_func(
                    name, session=session, user=user, conversation_id=conversation_id
                ),
                name=spec.name.value,
                description=spec.description,
                args_schema=spec.input_model,
            )
        )
    return tools


__all__ = ["SHOPPING_TOOL_NAMES", "build_shopping_tools"]
