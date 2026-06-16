"""Turn runner — drive the graph + emit contract-v0 SSE events (US-E5-03/04, ADR-0031).

Bridges the LangGraph orchestrator (``graph.py``) to the agent SSE endpoint
(``app/api/routers/agent.py``). For one user turn it:

  1. opens/loads the conversation (the ``thread_id`` for the graph + the durable record),
  2. persists the user message,
  3. invokes the graph; if it pauses at the checkout-approval ``interrupt()`` it surfaces
     the plan as an SSE frame and stops (the turn resumes on a later approval call),
  4. persists the assistant message + emits ``token -> citations -> done`` SSE frames.

The SSE wire shape is the LOCKED contract (``app/schemas/agent.py``):
``event: token`` (text deltas) -> ``event: citations`` -> ``event: done`` (terminal:
conversation_id + message_id + action). A pause adds an ``event: approval`` frame before
``done`` so the client can render the approval gate. Errors surface as ``event: error``.

The chat model / brains are injected via ``GraphDeps`` so a turn is testable with a stub
brain and no provider key. ``compiled_graph`` is injectable for the same reason (a test
passes one wired with a ``MemorySaver``).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent import persistence
from app.agent.graph import (
    Command,
    GraphDeps,
    build_graph,
    make_config,
    user_turn,
)
from app.agent.trace import set_disposition, trace_turn
from app.db.models import User
from app.schemas.agent import AgentActionOut, DoneEvent
from app.schemas.enums import ConversationSurface, MessageRole


def _sse(event: str, data: object) -> str:
    """Encode one SSE frame (matches the router's ``_sse_frame``)."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@dataclass
class TurnResult:
    """The outcome of driving the graph for one turn (before SSE encoding)."""

    conversation_id: str
    final_text: str
    action: dict[str, Any] | None
    awaiting_approval: bool
    approval_payload: dict[str, Any] | None
    citations: list[dict[str, Any]] = field(default_factory=list)


def _pending_interrupt(graph: Any, config: dict[str, Any]) -> dict[str, Any] | None:
    """Return the interrupt payload if the thread is paused at one, else None.

    LangGraph surfaces a pending ``interrupt()`` via the checkpointed state's tasks
    (``get_state(config).tasks[].interrupts``), not the ``invoke`` return value — so we
    read it from the graph state after invoking.
    """
    state = graph.get_state(config)
    for task in getattr(state, "tasks", ()):  # PregelTask
        for itr in getattr(task, "interrupts", ()):  # Interrupt
            value = getattr(itr, "value", itr)
            return value if isinstance(value, dict) else {"value": value}
    return None


def _resolve_seller_store_id(session: Session, user: User) -> str | None:
    """The seller's store id (for merch scope), resolved from identity — never the model."""
    from app.db.models import Store

    return session.scalar(select(Store.id).where(Store.owner_id == user.id))


def run_turn(
    *,
    session: Session,
    user: User,
    text: str,
    conversation_id: str | None = None,
    surface: ConversationSurface = ConversationSurface.buyer,
    deps_overrides: dict[str, Any] | None = None,
    compiled_graph: Any | None = None,
    session_factory: Any | None = None,
) -> TurnResult:
    """Drive the graph for a new user message; persist the turn; return the result.

    If ``conversation_id`` is None a new conversation is opened. ``deps_overrides`` lets a
    test inject a stub ``classifier`` / ``planner`` (no provider key). ``compiled_graph``
    lets a test reuse one graph (with its checkpointer) across the run + resume.
    ``session_factory`` (if given) lets off-critical-path work (async merch generation)
    commit on its own session; the seller store scope is resolved from the user identity.
    """
    graph = compiled_graph or build_graph()

    if conversation_id is None:
        convo = persistence.open_conversation(session, user=user, surface=surface)
        conversation_id = convo.id

    persistence.append_message(
        session,
        conversation_id=conversation_id,
        role=MessageRole.user,
        content=text,
    )

    overrides = dict(deps_overrides or {})
    # Identity-derived scope (never from the model): the seller's own store for merch.
    if "seller_store_id" not in overrides:
        overrides["seller_store_id"] = _resolve_seller_store_id(session, user)
    if session_factory is not None and "session_factory" not in overrides:
        overrides["session_factory"] = session_factory

    deps = GraphDeps(
        session=session,
        user=user,
        conversation_id=conversation_id,
        **overrides,
    )
    config = make_config(deps, thread_id=conversation_id)

    # Observability (best-effort): one trace per turn — per-node spans, tool calls, model
    # calls (tokens/cost), and the final disposition (US-E7-04, ADR-0042 §D1). A tracing
    # fault never breaks the turn; tracing is a pure no-op when OBS_ENABLED is false.
    with trace_turn(conversation_id=conversation_id):
        result = graph.invoke(user_turn(text), config)

        interrupt_payload = _pending_interrupt(graph, config)
        if interrupt_payload is not None:
            # Paused at the approval gate — DO NOT persist an assistant message yet; the turn
            # finishes on approval/rejection. Surface the plan for the client to act on.
            set_disposition("checkout_proposed")
            return TurnResult(
                conversation_id=conversation_id,
                final_text=interrupt_payload.get("summary", ""),
                action=None,
                awaiting_approval=True,
                approval_payload=interrupt_payload,
            )

        set_disposition(_disposition_of(result))
        return _finalize(session, conversation_id, result)


def resume_turn(
    *,
    session: Session,
    conversation_id: str,
    user: User,
    approved: bool,
    ship_address: dict[str, Any] | None = None,
    deps_overrides: dict[str, Any] | None = None,
    compiled_graph: Any,
) -> TurnResult:
    """Resume a turn paused at the checkout-approval interrupt.

    ``approved=True`` runs the real ``draftOrder`` (places the order); anything else ends
    the turn with no side effect. ``compiled_graph`` MUST be the same graph instance (same
    checkpointer) that produced the interrupt, so the thread resumes.
    """
    deps = GraphDeps(
        session=session,
        user=user,
        conversation_id=conversation_id,
        **(deps_overrides or {}),
    )
    config = make_config(deps, thread_id=conversation_id)
    resume_value: dict[str, Any] = {"approved": approved}
    if ship_address is not None:
        resume_value["ship_address"] = ship_address
    with trace_turn(conversation_id=conversation_id):
        result = compiled_graph.invoke(Command(resume=resume_value), config)
        set_disposition(_disposition_of(result))
        return _finalize(session, conversation_id, result)


_FALLBACK_MARKER = "I wasn't able to finish that"


def _disposition_of(result: dict[str, Any]) -> str:
    """Classify the turn's terminal disposition for the trace (US-E7-04).

    reply | clarify | refusal | fallback. (checkout_proposed is set on the interrupt path.)
    A refused-outcome action -> ``refusal``; the clarifying flag -> ``clarify``; the
    graceful step-budget apology -> ``fallback``; otherwise a plain ``reply``.
    """
    action = result.get("action")
    if isinstance(action, dict) and action.get("outcome") == "refused":
        return "refusal"
    if result.get("clarifying"):
        return "clarify"
    if _FALLBACK_MARKER in str(result.get("final_text", "")):
        return "fallback"
    return "reply"


def _finalize(
    session: Session, conversation_id: str, result: dict[str, Any]
) -> TurnResult:
    """Persist the assistant message and package the terminal result."""
    final_text = result.get("final_text", "")
    action = result.get("action")
    citations = result.get("citations") or []
    persistence.append_message(
        session,
        conversation_id=conversation_id,
        role=MessageRole.assistant,
        content=final_text,
    )
    return TurnResult(
        conversation_id=conversation_id,
        final_text=final_text,
        action=action,
        awaiting_approval=False,
        approval_payload=None,
        citations=citations,
    )


def stream_turn(
    *,
    session: Session,
    user: User,
    text: str,
    conversation_id: str | None = None,
    surface: ConversationSurface = ConversationSurface.buyer,
    deps_overrides: dict[str, Any] | None = None,
    compiled_graph: Any | None = None,
    session_factory: Any | None = None,
) -> Iterator[str]:
    """Run a turn and yield contract-v0 SSE frames (token -> [approval] -> citations -> done).

    Used by the ``/agent`` SSE routes. The turn is computed, then chunked into token
    frames (the runtime LLM streaming is wired in a later story; the contract shape is
    honored today). A pause at the approval gate emits an ``approval`` frame and a ``done``
    whose ``action`` reflects the deferral; the client resumes via the approval endpoint.
    """
    try:
        result = run_turn(
            session=session,
            user=user,
            text=text,
            conversation_id=conversation_id,
            surface=surface,
            deps_overrides=deps_overrides,
            compiled_graph=compiled_graph,
            session_factory=session_factory,
        )
    except Exception as exc:  # noqa: BLE001 - surface as a stream-level error frame
        yield _sse(
            "error",
            {"error": {"code": "internal_error", "message": str(exc)}},
        )
        return

    # token frames — chunk the final/approval text so the client renders progressively.
    for chunk in _chunk(result.final_text):
        yield _sse("token", chunk)

    if result.awaiting_approval and result.approval_payload is not None:
        yield _sse("approval", result.approval_payload)

    yield _sse("citations", result.citations)

    action_out: AgentActionOut | None = None
    if result.action is not None:
        action_out = AgentActionOut(
            id="",
            action_type=result.action.get("action_type", "none"),
            outcome=result.action.get("outcome", "applied"),
            payload=result.action.get("payload", {}),
        )
    done = DoneEvent(
        conversation_id=result.conversation_id,
        message_id="",
        action=action_out,
    )
    yield _sse("done", done.model_dump(mode="json"))


def _chunk(text: str, size: int = 24) -> Iterator[str]:
    if not text:
        return
    for i in range(0, len(text), size):
        yield text[i : i + size]


__all__ = [
    "TurnResult",
    "resume_turn",
    "run_turn",
    "stream_turn",
]
