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

from app.api._contract import ERROR_RESPONSES, stub
from app.schemas.agent import (
    CitationsEvent,
    ConversationOut,
    ConversationStartRequest,
    DoneEvent,
    MessageRequest,
    StreamError,
    TokenEvent,
)
from app.schemas.envelope import CamelModel, Envelope

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


def _illustrative_stream() -> Iterator[str]:
    """A tiny, typed example turn so the contract's SSE shape is demonstrable.

    Week-2 replaces this with the real agent loop (retrieve → ground → act → persist).
    The event ORDER and payload TYPES here are the locked contract; the strings are
    placeholder. ``StreamError`` is imported to document the error frame's shape.
    """
    _ = StreamError  # documented error-frame payload; not emitted on the happy path
    yield _sse_frame("token", TokenEvent(delta="contract-draft: ").delta)
    yield _sse_frame("token", TokenEvent(delta="SSE agent turn (US-E4-00).").delta)
    yield _sse_frame("citations", CitationsEvent().model_dump(mode="json")["citations"])
    yield _sse_frame(
        "done",
        DoneEvent(
            conversation_id="00000000-0000-0000-0000-000000000000",
            message_id="00000000-0000-0000-0000-000000000000",
        ).model_dump(mode="json"),
    )


@router.post(
    "/conversations",
    status_code=status.HTTP_201_CREATED,
    summary="Start a conversation (buyer|support|seller surface) — SSE reply",
    response_class=StreamingResponse,
    responses=_SSE_RESPONSE,
)
def start_conversation(body: ConversationStartRequest) -> StreamingResponse:
    """Open a conversation; if a first message is included, the assistant turn streams
    back as ``text/event-stream`` (token → citations → done). (J-BUY-01/02, J-SUP-02,
    J-SEL-03)
    """
    return StreamingResponse(
        _illustrative_stream(), media_type="text/event-stream"
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
def get_conversation(conversation_id: str) -> Envelope[ConversationOut]:
    """Full conversation transcript incl. citations on assistant messages."""
    stub()


@router.post(
    "/conversations/{conversation_id}/messages",
    summary="Send a message; assistant reply streams back as SSE (grounded + cited)",
    response_class=StreamingResponse,
    responses=_SSE_RESPONSE,
)
def post_message(
    conversation_id: str, body: MessageRequest
) -> StreamingResponse:
    """User message in (JSON); assistant turn streams out as ``text/event-stream``.

    Frames: ``token`` (deltas) → ``citations`` → ``done`` (terminal: persisted
    ``action`` whose outcome is applied | refused | hitl_deferred, plus conversation_id
    + message_id). (J-BUY-03/06, J-SUP-02/03)
    """
    return StreamingResponse(
        _illustrative_stream(), media_type="text/event-stream"
    )
