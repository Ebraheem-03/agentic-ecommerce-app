"""Agent SSE endpoint E2E — the streamable graph wired into /agent (US-E5-03/04, ADR-0031).

Drives the real ASGI app (`persona_client` + `seeded_db`) against the now-live `/agent`
routes. The chat model is never built: the router's `_DEPS_OVERRIDES` seam injects a stub
classifier/planner so the streaming turn runs with NO provider key (CI-safe). Asserts the
contract-v0 SSE shape (token → citations → done) on a real auth-scoped streamed turn, plus
the durable transcript GET reads back the persisted conversation.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

import app.api.routers.agent as agent_router
from app.agent.brains import IntentResult, PlannerStep
from tests.conftest import ContractClient, SeededDb


class _StubClassifier:
    def classify(self, history: list[Any]) -> IntentResult:
        return IntentResult(route="shopping", confidence=0.9)


class _StubPlanner:
    def plan(self, history: list[Any], tool_results: list[str]) -> PlannerStep:
        return PlannerStep(reply="Here are a few things you might like.")


@pytest.fixture
def stub_brains() -> Iterator[None]:
    """Install stub brains on the SSE path so the turn needs no provider key."""
    agent_router._DEPS_OVERRIDES = {
        "classifier": _StubClassifier(),
        "planner": _StubPlanner(),
    }
    try:
        yield
    finally:
        agent_router._DEPS_OVERRIDES = None


def _events(body: str) -> list[tuple[str, str]]:
    """Parse an SSE body into (event, data) pairs."""
    out: list[tuple[str, str]] = []
    event = data = None
    for line in body.splitlines():
        if line.startswith("event:"):
            event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data = line[len("data:") :].strip()
        elif not line.strip() and event is not None:
            out.append((event, data or ""))
            event = data = None
    return out


@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_start_conversation_streams_contract_events(
    seeded_db: SeededDb, persona_client: ContractClient, stub_brains: None
) -> None:
    """POST /agent/conversations returns text/event-stream with token→citations→done."""
    resp = persona_client.post(
        "/agent/conversations",
        json={"surface": "buyer", "message": "show me something nice"},
    )
    assert resp.status_code == 201
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _events(resp.text)
    names = [e for e, _ in events]
    assert "token" in names
    assert names[-2:] == ["citations", "done"]  # terminal order

    # done carries the persisted conversation id.
    done = next(d for e, d in events if e == "done")
    assert "conversation_id" in done


def test_unauth_conversation_is_401(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    """No Bearer token → 401 (the SSE routes are auth-scoped via require_user)."""
    resp = api_client.post("/agent/conversations", json={"message": "hi"})
    assert resp.status_code == 401


@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_transcript_get_reads_persisted_turn(
    seeded_db: SeededDb, persona_client: ContractClient, stub_brains: None
) -> None:
    """After a streamed turn, the JSON transcript GET reads back the durable record."""
    start = persona_client.post(
        "/agent/conversations", json={"message": "hello there"}
    )
    done = next(d for e, d in _events(start.text) if e == "done")
    import json

    convo_id = json.loads(done)["conversation_id"]

    resp = persona_client.get(f"/agent/conversations/{convo_id}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    roles = [m["role"] for m in data["messages"]]
    assert roles == ["user", "assistant"]
