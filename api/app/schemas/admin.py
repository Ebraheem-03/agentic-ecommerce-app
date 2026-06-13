"""Admin surfaces: policy review/edit + agent guardrail config.

Implied by J-ADM-01..03. Policies are the RAG source the support agent retrieves over;
editing one must observably change agent behavior (re-embed on write — Echo's concern).
Guardrail config is stored as a policy of kind ``platform`` in v0 (no new table); this
is flagged as an open question in contract-v0.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.enums import PolicyKind
from app.schemas.envelope import CamelModel


class PolicyOut(CamelModel):
    """A policy document."""

    id: str
    store_id: str | None = None
    kind: PolicyKind
    title: str
    body: str
    is_active: bool
    version: int
    effective_from: datetime
    updated_at: datetime


class PolicyUpsert(CamelModel):
    """POST/PUT /admin/policies — create or edit a policy (re-embeds on write)."""

    store_id: str | None = None
    kind: PolicyKind
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)
    is_active: bool = True
