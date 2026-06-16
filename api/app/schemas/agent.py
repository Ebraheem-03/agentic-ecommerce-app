"""Agent (Ember) conversational endpoints.

The contract Echo (Week-2) implements against. A user message goes in (plain JSON
``MessageRequest`` / ``ConversationStartRequest``); the assistant turn comes back as an
**SSE stream** (``text/event-stream``), NOT a single JSON body. RATIFIED 2026-06-14
([REVIEW] decision 5; see ADR-0021). Everything still persists to conversations /
messages / agent_actions; ``outcome`` is one of applied | refused | hitl_deferred.
Provider/model-agnostic: no Groq/Gemini specifics leak into the contract.

SSE event protocol (the wire shape Echo emits and Iris/Echo's generative-UI surface
consumes):

  - ``event: token``     ``data: "<text delta>"``        — assistant message, chunk-wise
                                                           (repeated 0..n times).
  - ``event: citations`` ``data: [Citation, ...]``        — grounding citations; emitted
                                                           when known (may follow tokens).
  - ``event: done``      ``data: DoneEvent``              — TERMINAL: persisted action +
                                                           conversation_id + message_id.
  - ``event: error``     ``data: StreamError``            — stream-level failure; carries
                                                           the canonical error envelope.

The ``*Event`` models below type each ``data:`` payload so the shape is verifiable and
shows in the contract doc / Scalar page. The transport is the stream; these are the
JSON-serialized payloads carried inside each frame.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.catalog import ProductSummary
from app.schemas.enums import AgentOutcome, ConversationSurface, MessageRole
from app.schemas.envelope import CamelModel, ErrorBody


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
    """POST /agent/conversations — open a conversation on a surface.

    The REQUEST side is plain JSON (unchanged by the SSE ruling). If ``message`` is
    present, the response is the assistant turn streamed as ``text/event-stream``;
    otherwise the conversation is opened and the empty stream closes immediately.
    """

    surface: ConversationSurface = ConversationSurface.buyer
    context_order_id: str | None = None
    context_product_id: str | None = None
    # Optional first message; if present, the SSE stream carries the first reply.
    message: str | None = Field(default=None, max_length=4000)


class MessageRequest(CamelModel):
    """POST /agent/conversations/{id}/messages — continue a conversation.

    Plain-JSON request; the assistant reply streams back as ``text/event-stream``.
    """

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


class ConversationOut(CamelModel):
    """A conversation with its message history.

    Returned (plain JSON) by the transcript GET — that read is NOT streamed. The
    live assistant turn is delivered over SSE; this is the durable record of it.
    """

    id: str
    surface: ConversationSurface
    context_order_id: str | None = None
    context_product_id: str | None = None
    messages: list[MessageOut]
    created_at: datetime


# --------------------------------------------------------------------------- #
# SSE event payloads — the JSON carried inside each ``text/event-stream`` frame. #
# RATIFIED 2026-06-14 ([REVIEW] decision 5; ADR-0021).                          #
# Each model below is the ``data:`` payload for one named ``event:``.           #
# --------------------------------------------------------------------------- #
class TokenEvent(CamelModel):
    """``event: token`` — one assistant text delta. Emitted 0..n times, in order.

    The raw wire ``data:`` for a token frame is the bare ``delta`` string; this model
    documents/types that payload (``{"delta": "<text>"}`` when serialized as an object,
    or the bare string on the wire — Echo emits the string, this names the field).
    """

    delta: str = Field(description="A chunk of assistant text to append to the message.")


class CitationsEvent(CamelModel):
    """``event: citations`` — grounding citations for the turn.

    Emitted once, when retrieval is resolved; MAY arrive after some ``token`` frames.
    Each entry is a ``Citation`` (→ an ``embedding_source`` product/policy row + chunk).
    """

    citations: list[Citation] = Field(default_factory=list)


class DoneEvent(CamelModel):
    """``event: done`` — TERMINAL frame. The persisted turn, ids, and final action.

    Carries the ``agent_actions`` row this turn produced (``action``; null for a pure
    clarify/refusal-with-no-side-effect), any grounded ``recommendations`` finalized for
    the turn, and the persisted ``conversation_id`` + assistant ``message_id`` so the
    client can reconcile with the transcript GET. After ``done`` the stream closes.
    """

    conversation_id: str
    message_id: str = Field(description="Id of the persisted assistant message.")
    action: AgentActionOut | None = None
    recommendations: list[RecommendationOut] = Field(default_factory=list)


class StreamError(CamelModel):
    """``event: error`` — a stream-level failure.

    Carries the canonical error envelope's inner body (``ErrorBody``: closed ``code`` +
    message + optional details) so a mid-stream failure is as machine-checkable as a
    non-2xx JSON error. The stream closes after this frame.
    """

    error: ErrorBody


# --------------------------------------------------------------------------- #
# Merchandising draft (US-E5-08, ADR-0034 §3).                                  #
# --------------------------------------------------------------------------- #
class ComparableOut(CamelModel):
    """One real catalog comparable behind a price suggestion — the surfaced BASIS.

    The merchandising agent's price suggestion is grounded in REAL seeded same-category /
    similar catalog rows (never invented competitor data). Each comparable names the
    product + the actual lowest active variant price the suggestion is computed from, so
    the seller sees *why* the number is what it is.
    """

    product_id: str
    title: str
    slug: str
    price_minor: int = Field(description="Lowest active variant price (minor units).")


class PriceSuggestionOut(CamelModel):
    """A comparables-based price suggestion with its basis (never an opaque number).

    ``suggested_price_minor`` is computed structurally (median of the comparables' prices),
    NOT by the model. ``basis`` is the human-readable rationale; ``comparables`` are the
    real catalog rows it was derived from. Empty comparables -> no suggestion (null price).
    """

    suggested_price_minor: int | None = None
    currency: str = "USD"
    basis: str = Field(description="How the suggestion was derived (the surfaced basis).")
    comparables: list[ComparableOut] = Field(default_factory=list)


class MerchDraftOut(CamelModel):
    """A generated DRAFT listing + comparables price suggestion (US-E5-08).

    Persisted as a DRAFT product (``status='draft'``) — NEVER published to the live
    catalog (a seller approves before anything goes live; that publish action is a future
    story). ``draft_product_id`` is the persisted draft's id so a later approval step can
    resolve it. Generation runs async (off the request critical path); the draft is
    retrievable once ready.
    """

    draft_product_id: str
    status: Literal["draft"] = "draft"
    title: str
    description: str
    category: str = ""
    attributes: dict[str, str] = Field(default_factory=dict)
    price_suggestion: PriceSuggestionOut
