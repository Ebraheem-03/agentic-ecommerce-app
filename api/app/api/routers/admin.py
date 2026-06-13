"""Admin routes (contract draft): policy + guardrail management."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api._contract import ERROR_RESPONSES, stub
from app.schemas.admin import PolicyOut, PolicyUpsert
from app.schemas.envelope import Envelope, ListEnvelope

router = APIRouter(prefix="/admin", tags=["admin"], responses=ERROR_RESPONSES)


@router.get(
    "/policies",
    response_model=ListEnvelope[PolicyOut],
    summary="Review catalog policies / guardrails",
)
def list_policies(
    kind: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
) -> ListEnvelope[PolicyOut]:
    """List policies (the agent's RAG source + platform guardrails). (J-ADM-01)"""
    stub()


@router.post(
    "/policies",
    response_model=Envelope[PolicyOut],
    status_code=status.HTTP_201_CREATED,
    summary="Create a policy (re-embeds on write)",
)
def create_policy(body: PolicyUpsert) -> Envelope[PolicyOut]:
    """Create a policy; triggers re-embed so agent behavior changes. (J-ADM-02)"""
    stub()


@router.put(
    "/policies/{policy_id}",
    response_model=Envelope[PolicyOut],
    summary="Edit a policy (re-embeds; bumps version)",
)
def update_policy(policy_id: str, body: PolicyUpsert) -> Envelope[PolicyOut]:
    """Edit a policy. Observably alters agent behavior (regression-checked). (J-ADM-02)"""
    stub()
