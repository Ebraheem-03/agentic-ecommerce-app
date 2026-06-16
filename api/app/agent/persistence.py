"""Durable conversation state — conversations / messages (US-E5-03, ADR-0031).

The LangGraph checkpointer holds *in-graph* thread state (so an ``interrupt()`` can be
resumed). The DURABLE record of the conversation — the turns a user and the support team
can read back — lives in OUR tables (``conversations`` / ``messages``; ``agent_actions``
is written by the tool executor). ``thread_id`` == ``conversation.id`` ties the two
together: the graph keys its checkpoint on the same id this module persists rows under.

This module is intentionally small: open/lookup a conversation, append a user or
assistant message. It does NOT own the graph or the LLM — it is the persistence seam the
orchestrator writes through so the transcript GET (``/agent/conversations/{id}``) reads a
real record, not graph-internal state.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Conversation, Message
from app.db.models.user import User
from app.schemas.agent import Citation
from app.schemas.enums import ConversationSurface, MessageRole


def open_conversation(
    session: Session,
    *,
    user: User,
    surface: ConversationSurface = ConversationSurface.buyer,
    context_order_id: str | None = None,
    context_product_id: str | None = None,
) -> Conversation:
    """Create + persist a new conversation; its id is the graph ``thread_id``."""
    convo = Conversation(
        user_id=user.id,
        surface=surface.value,
        context_order_id=context_order_id,
        context_product_id=context_product_id,
    )
    session.add(convo)
    session.flush()  # assign the PK so callers get the thread_id immediately
    return convo


def get_conversation(session: Session, conversation_id: str) -> Conversation | None:
    """Look up a conversation by id (the thread_id). ``None`` if absent."""
    return session.get(Conversation, conversation_id)


def append_message(
    session: Session,
    *,
    conversation_id: str,
    role: MessageRole,
    content: str,
    citations: list[Citation] | None = None,
) -> Message:
    """Append + persist one message turn to a conversation."""
    msg = Message(
        conversation_id=conversation_id,
        role=role.value,
        content=content,
        citations=[c.model_dump(mode="json") for c in (citations or [])],
    )
    session.add(msg)
    session.flush()
    return msg


__all__ = ["append_message", "get_conversation", "open_conversation"]
