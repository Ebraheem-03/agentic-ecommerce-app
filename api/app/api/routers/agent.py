"""Agent (Ember) conversational routes (contract draft).

The contract Echo implements in Week-2. The assistant turn is an **SSE stream**
(``text/event-stream``), RATIFIED 2026-06-14 ([REVIEW] decision 5; ADR-0021) — NOT a
single JSON body. The request side stays plain JSON. The transcript GET stays plain
JSON (it is a read of the persisted conversation, not the live turn).

The two message-producing routes advertise a ``200`` whose content type is
``text/event-stream`` so the OpenAPI/Scalar page makes the streaming nature explicit.
Their stub yields a tiny illustrative ``token → citations → done`` sequence so the
shape is demonstrable; Week-2 swaps in the real agent loop.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

import app.core.config as app_config
from app.agent import persistence
from app.agent.runner import stream_turn
from app.api._contract import ERROR_RESPONSES, stub
from app.api.deps import CurrentUser, _factory_for
from app.core.errors import APIError
from app.db.models import User
from app.schemas.agent import (
    Citation,
    CitationsEvent,
    ConversationOut,
    ConversationStartRequest,
    DoneEvent,
    MessageOut,
    MessageRequest,
    StreamError,
    TokenEvent,
)
from app.schemas.enums import ConversationSurface, MessageRole
from app.schemas.envelope import CamelModel, Envelope, ErrorCode

router = APIRouter(prefix="/agent", tags=["agent"], responses=ERROR_RESPONSES)

# OpenAPI ``responses`` entry that documents the SSE turn on the streaming routes.
# Scalar renders this so a reader sees ``text/event-stream`` (a stream), not a JSON body.
_SSE_RESPONSE: dict[int | str, dict[str, object]] = {
    200: {
        "description": (
            "Server-Sent Events stream (text/event-stream). Frames, in order:\n"
            "- `event: token` data: `<text delta>` (TokenEvent) — repeated 0..n.\n"
            "- `event: citations` data: `[Citation, ...]` (CitationsEvent) — once.\n"
            "- `event: done` data: `DoneEvent` — TERMINAL: persisted action + "
            "conversation_id + message_id.\n"
            "- `event: error` data: `StreamError` — canonical error envelope on "
            "stream-level failure."
        ),
        "content": {
            "text/event-stream": {
                "schema": {
                    "type": "string",
                    "example": (
                        'event: token\ndata: "Let me check"\n\n'
                        'event: token\ndata: " our stock."\n\n'
                        'event: citations\ndata: [{"source_type":"product",'
                        '"source_id":"...","chunk_index":0,"snippet":"...",'
                        '"score":0.82}]\n\n'
                        'event: done\ndata: {"conversation_id":"...",'
                        '"message_id":"...","action":null,"recommendations":[]}\n\n'
                    ),
                }
            }
        },
    },
}


def _sse_frame(event: str, data: object) -> str:
    """Encode one SSE frame: ``event: <name>\\ndata: <json>\\n\\n``."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _turn_session() -> Session:
    """A dedicated Session for one streamed turn, bound to the current settings URL.

    A ``StreamingResponse`` body runs AFTER the request's dependencies close, so the turn
    can't borrow the ``get_session`` dependency's session (it would already be committed/
    closed). The streaming generator opens + commits + closes this session itself.
    """
    factory = _factory_for(app_config.settings.database_url)
    return factory()


# Test/injection seam: when set (e.g. a fixture installs a stub classifier/planner), the
# SSE turn runs WITHOUT a provider key so the streaming path is CI-testable. Production
# leaves this None and the runner resolves the real Groq/Gemini chat model from settings.
_DEPS_OVERRIDES: dict[str, object] | None = None


def _agent_stream(
    *, user: User, text: str, conversation_id: str | None, surface: ConversationSurface
) -> Iterator[str]:
    """Drive a real agent turn and yield contract SSE frames, owning the session txn.

    Uses the default (LLM-backed) brains unless ``_DEPS_OVERRIDES`` injects a stub (tests);
    the chat model is resolved from settings (Groq by default). On any failure an ``error``
    frame is emitted (StreamError shape) and the session rolls back. ``TokenEvent`` /
    ``CitationsEvent`` types document the frame payloads the runner emits.
    """
    _ = (TokenEvent, CitationsEvent, StreamError)  # frame payload types (documented)
    session = _turn_session()
    try:
        yield from stream_turn(
            session=session,
            user=user,
            text=text,
            conversation_id=conversation_id,
            surface=surface,
            deps_overrides=_DEPS_OVERRIDES,
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001 - emit a stream-level error, never raise mid-body
        session.rollback()
        yield _sse_frame("error", {"error": {"code": "internal_error", "message": str(exc)}})
    finally:
        session.close()


@router.post(
    "/conversations",
    status_code=status.HTTP_201_CREATED,
    summary="Start a conversation (buyer|support|seller surface) — SSE reply",
    response_class=StreamingResponse,
    responses=_SSE_RESPONSE,
)
def start_conversation(
    body: ConversationStartRequest, user: CurrentUser
) -> StreamingResponse:
    """Open a conversation; if a first message is included, the assistant turn streams
    back as ``text/event-stream`` (token → citations → done). (J-BUY-01/02, J-SUP-02,
    J-SEL-03)

    Auth-scoped: the acting user is resolved via ``require_user`` (one identity path for
    humans + agents). The orchestrator graph classifies intent, routes to the shopping
    agent (support/merch are deferred), and persists the turn to conversations/messages.
    """
    surface = ConversationSurface(body.surface.value)
    return StreamingResponse(
        _agent_stream(
            user=user,
            text=body.message or "",
            conversation_id=None,
            surface=surface,
        ),
        status_code=status.HTTP_201_CREATED,
        media_type="text/event-stream",
    )


class SseEventCatalog(CamelModel):
    """Documentation model: the typed payload of each SSE ``data:`` frame.

    The agent turn is a ``text/event-stream`` (see the two POST routes above), so the
    per-frame payloads can't be a route ``response_model``. This model surfaces them as
    NAMED schemas on the Scalar/OpenAPI page so the contract for each ``event:`` is
    verifiable. It is reference-only — no route returns it as data.
    """

    token: TokenEvent
    citations: CitationsEvent
    done: DoneEvent
    error: StreamError


@router.get(
    "/_sse-events",
    response_model=Envelope[SseEventCatalog],
    summary="SSE event payload reference (typed shapes for token|citations|done|error)",
)
def sse_event_reference() -> Envelope[SseEventCatalog]:
    """Reference-only: documents the typed ``data:`` payload of each agent SSE frame.

    Not a live data route — the actual turn streams from the two POST routes above as
    ``text/event-stream``. This exists so each event's shape renders in Scalar.
    """
    stub()


@router.get(
    "/conversations/{conversation_id}",
    response_model=Envelope[ConversationOut],
    summary="Get a conversation with its message history (JSON, not streamed)",
)
def get_conversation(
    conversation_id: str, user: CurrentUser
) -> Envelope[ConversationOut]:
    """Full conversation transcript incl. citations on assistant messages.

    Reads the DURABLE record (conversations/messages) — not graph-internal state. A
    foreign conversation surfaces as ``not_found`` (no existence leak), matching the
    handlers' owner-scoping convention.
    """
    from app.api.deps import get_session

    session = next(get_session())
    try:
        convo = persistence.get_conversation(session, conversation_id)
        if convo is None or (convo.user_id is not None and convo.user_id != user.id):
            raise APIError(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.not_found,
                message="We couldn't find that conversation.",
            )
        out = ConversationOut(
            id=convo.id,
            surface=ConversationSurface(convo.surface),
            context_order_id=convo.context_order_id,
            context_product_id=convo.context_product_id,
            created_at=convo.created_at,
            messages=[
                MessageOut(
                    id=m.id,
                    conversation_id=m.conversation_id,
                    role=MessageRole(m.role),
                    content=m.content,
                    citations=[Citation.model_validate(c) for c in m.citations],
                    created_at=m.created_at,
                )
                for m in sorted(convo.messages, key=lambda m: m.created_at)
            ],
        )
        return Envelope(data=out)
    finally:
        session.close()


@router.post(
    "/conversations/{conversation_id}/messages",
    summary="Send a message; assistant reply streams back as SSE (grounded + cited)",
    response_class=StreamingResponse,
    responses=_SSE_RESPONSE,
)
def post_message(
    conversation_id: str, body: MessageRequest, user: CurrentUser
) -> StreamingResponse:
    """User message in (JSON); assistant turn streams out as ``text/event-stream``.

    Frames: ``token`` (deltas) → ``citations`` → ``done`` (terminal: persisted
    ``action`` whose outcome is applied | refused | hitl_deferred, plus conversation_id
    + message_id). (J-BUY-03/06, J-SUP-02/03)
    """
    return StreamingResponse(
        _agent_stream(
            user=user,
            text=body.content,
            conversation_id=conversation_id,
            surface=ConversationSurface.buyer,
        ),
        media_type="text/event-stream",
    )
