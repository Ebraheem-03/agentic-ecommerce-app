"""Agent (Ember) conversational endpoints.

The contract Echo (Week-2) implements against. A user message goes in; an assistant
message comes out WITH citations and an optional agent action whose ``outcome`` is one
of applied | refused | hitl_deferred. Everything persists to conversations / messages /
agent_actions. Provider/model-agnostic: no Groq/Gemini specifics leak into the contract.

v0 response is a single JSON message (NOT streamed) — see contract-v0 [REVIEW].
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.catalog import ProductSummary
from app.schemas.enums import AgentOutcome, ConversationSurface, MessageRole
from app.schemas.envelope import CamelModel


class Citation(CamelModel):
    """A grounding citation backing an assistant claim.

    ``source_type`` mirrors the ``embedding_source`` enum (product | policy); the
    citation points at the retrieved source row + chunk so the UI can render a
    verifiable reference (``data-testid="agent-citation"``).
    """

    source_type: Literal["product", "policy"]
    source_id: str
    chunk_index: int = Field(default=0, ge=0)
    snippet: str = Field(description="The retrieved text the claim is grounded in.")
    score: float | None = None


class RecommendationOut(CamelModel):
    """A grounded product recommendation with a stated reason.

    Backs ``agent-recommendation-card`` + ``agent-recommendation-reason``.
    """

    product: ProductSummary
    reason: str = Field(description="Why the agent picked this — defensible, grounded.")


class AgentActionOut(CamelModel):
    """An action the agent took/attempted in service of the turn.

    Mirrors ``agent_actions`` (action_type, payload, outcome). ``outcome`` =
    hitl_deferred means a human must complete it (e.g. out-of-window return).
    """

    id: str
    action_type: str = Field(description="e.g. add_to_cart, request_return, none.")
    outcome: AgentOutcome
    payload: dict[str, object] = Field(default_factory=dict)


class ConversationStartRequest(CamelModel):
    """POST /agent/conversations — open a conversation on a surface."""

    surface: ConversationSurface = ConversationSurface.buyer
    context_order_id: str | None = None
    context_product_id: str | None = None
    # Optional first message; if present, the response includes the first reply.
    message: str | None = Field(default=None, max_length=4000)


class MessageRequest(CamelModel):
    """POST /agent/conversations/{id}/messages — continue a conversation."""

    content: str = Field(min_length=1, max_length=4000)
    idempotency_key: str | None = Field(default=None, max_length=200)


class MessageOut(CamelModel):
    """A persisted message (user or assistant) with citations."""

    id: str
    conversation_id: str
    role: MessageRole
    content: str
    citations: list[Citation] = Field(default_factory=list)
    created_at: datetime


class AgentReply(CamelModel):
    """The assistant's turn: the message + any recs + the action taken.

    This is the response body for message-in endpoints. ``recommendations`` and
    ``action`` are optional; a pure clarify/refusal reply has neither.
    """

    message: MessageOut
    recommendations: list[RecommendationOut] = Field(default_factory=list)
    action: AgentActionOut | None = None


class ConversationOut(CamelModel):
    """A conversation with its message history."""

    id: str
    surface: ConversationSurface
    context_order_id: str | None = None
    context_product_id: str | None = None
    messages: list[MessageOut]
    created_at: datetime


class ConversationStartResponse(CamelModel):
    """Response to opening a conversation; ``reply`` set iff a first message was sent."""

    conversation: ConversationOut
    reply: AgentReply | None = None
