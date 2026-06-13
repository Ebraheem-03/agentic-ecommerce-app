"""Agent (Ember) conversational routes (contract draft).

The contract Echo implements in Week-2. Single-response (non-streamed) v0.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api._contract import ERROR_RESPONSES, stub
from app.schemas.agent import (
    AgentReply,
    ConversationOut,
    ConversationStartRequest,
    ConversationStartResponse,
    MessageRequest,
)
from app.schemas.envelope import Envelope

router = APIRouter(prefix="/agent", tags=["agent"], responses=ERROR_RESPONSES)


@router.post(
    "/conversations",
    response_model=Envelope[ConversationStartResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Start a conversation (buyer|support|seller surface)",
)
def start_conversation(
    body: ConversationStartRequest,
) -> Envelope[ConversationStartResponse]:
    """Open a conversation; if a first message is included, returns the first reply.
    (J-BUY-01/02, J-SUP-02, J-SEL-03)
    """
    stub()


@router.get(
    "/conversations/{conversation_id}",
    response_model=Envelope[ConversationOut],
    summary="Get a conversation with its message history",
)
def get_conversation(conversation_id: str) -> Envelope[ConversationOut]:
    """Full conversation transcript incl. citations on assistant messages."""
    stub()


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=Envelope[AgentReply],
    summary="Send a message and get the assistant reply (grounded + cited)",
)
def post_message(
    conversation_id: str, body: MessageRequest
) -> Envelope[AgentReply]:
    """User message in, assistant message out with citations + optional action.

    ``action.outcome`` is applied | refused | hitl_deferred. (J-BUY-03/06, J-SUP-02/03)
    """
    stub()
