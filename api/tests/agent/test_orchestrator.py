"""Orchestrator + shopping-agent graph tests (US-E5-03/04, ADR-0031).

DB-backed against the seeded throwaway DB (``seeded_db`` + ``handles`` spine,
``tests/conftest.py``). The chat model is NEVER constructed: every test injects a STUB
``classifier`` / ``planner`` (the ``brains`` injection seam) so CI runs with no provider
key — the human's hard requirement. The graph structure, routing policy, interrupt
approval gate, and real-service side effects are all exercised for real.

Coverage:
  * intent routing — each route (shopping/support/merchandising) + ambiguous→clarify;
  * deferred support/merch nodes return a graceful "not available yet" message;
  * a full shopping turn (discovery→cart) up to the checkout approval interrupt;
  * the HARD approval stop — interrupt fires BEFORE any order; resume(approved) places
    the order via the real draftOrder tool (reserve/capture path), resume(rejected) does
    not; an order is placed only on approval.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent import persistence
from app.agent.brains import IntentResult, PlannerStep, ToolCall
from app.agent.graph import MAX_PLAN_STEPS, build_graph
from app.agent.runner import resume_turn, run_turn
from app.db.models import AgentAction, Order, User
from tests.conftest import ResolvedHandles, SeededDb
from tests.fixtures.handles import PERSONAS


# --------------------------------------------------------------------------- #
# Stub brains — deterministic, no LLM. The injection seam from app.agent.brains. #
# --------------------------------------------------------------------------- #
class StubClassifier:
    def __init__(self, result: IntentResult) -> None:
        self._result = result

    def classify(self, history: list[Any]) -> IntentResult:
        return self._result


class StubPlanner:
    """Returns a scripted sequence of PlannerSteps, one per ``plan`` call."""

    def __init__(self, steps: list[PlannerStep]) -> None:
        self._steps = list(steps)
        self._i = 0

    def plan(self, history: list[Any], tool_results: list[str]) -> PlannerStep:
        step = self._steps[min(self._i, len(self._steps) - 1)]
        self._i += 1
        return step


def _user(seeded_db: SeededDb, handles: ResolvedHandles, persona: str) -> User:
    uid = handles.user_ids[PERSONAS[persona].handle]
    with Session(seeded_db.engine) as s:
        u = s.get(User, uid)
        assert u is not None
        return u


def _session(seeded_db: SeededDb) -> Session:
    return Session(seeded_db.engine)


def _order_count(session: Session, user: User) -> int:
    return (
        session.scalar(
            select(func.count()).select_from(Order).where(Order.user_id == user.id)
        )
        or 0
    )


# --------------------------------------------------------------------------- #
# Intent routing.                                                              #
# --------------------------------------------------------------------------- #
def test_merch_route_without_a_store_replies_gracefully(
    seeded_db: SeededDb,
    handles: ResolvedHandles,
) -> None:
    """A merch classification for a user with NO seller store replies gracefully (no draft).

    Merchandising is implemented (US-E5-08) — no longer a deferred stub. A buyer (no store)
    routed here gets the "which store is this for?" message and no action, rather than a
    draft being created.
    """
    user = _user(seeded_db, handles, "buyer_primary")
    classifier = StubClassifier(IntentResult(route="merchandising", confidence=0.95))
    with _session(seeded_db) as session:
        result = run_turn(
            session=session,
            user=user,
            text="hello",
            deps_overrides={"classifier": classifier},
        )
        session.commit()
    assert not result.awaiting_approval
    assert "which store" in result.final_text.lower()
    assert result.action is None


def test_ambiguous_routes_to_shopping_clarify(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """Low confidence → shopping agent with ONE clarifying turn (no guess, no dead-end)."""
    user = _user(seeded_db, handles, "buyer_primary")
    # Confidence below CLARIFY_THRESHOLD even though a route was guessed.
    classifier = StubClassifier(IntentResult(route="support", confidence=0.2))
    with _session(seeded_db) as session:
        result = run_turn(
            session=session,
            user=user,
            text="hmm",
            deps_overrides={"classifier": classifier},
        )
        session.commit()
    assert not result.awaiting_approval
    assert "shop for a product" in result.final_text  # the clarifying question
    assert result.action is None


def test_shopping_discovery_turn_persists(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """A confident shopping turn that searches then replies — persists user+assistant."""
    user = _user(seeded_db, handles, "buyer_primary")
    classifier = StubClassifier(IntentResult(route="shopping", confidence=0.9))
    planner = StubPlanner(
        [
            PlannerStep(tool_calls=[ToolCall(name="search", args={"query": "candle"})]),
            PlannerStep(reply="Here are some candles I found for you."),
        ]
    )
    with _session(seeded_db) as session:
        result = run_turn(
            session=session,
            user=user,
            text="show me candles",
            deps_overrides={"classifier": classifier, "planner": planner},
        )
        convo_id = result.conversation_id
        session.commit()
    assert "candles I found" in result.final_text

    with _session(seeded_db) as session:
        convo = persistence.get_conversation(session, convo_id)
        assert convo is not None
        roles = [m.role for m in sorted(convo.messages, key=lambda m: m.created_at)]
        assert roles == ["user", "assistant"]


# --------------------------------------------------------------------------- #
# DEFECT-D22-01 — planner loop-guard regression (ADR-0042 §D2).                 #
# --------------------------------------------------------------------------- #
class LoopingPlanner:
    """A planner that ALWAYS re-issues the identical search call (never flips to reply).

    Reproduces DEFECT-D22-01 key-free: under the real Groq model the
    ``LLMShoppingPlanner`` re-emitted the same ``search(...)`` every step and never replied,
    burning ``MAX_PLAN_STEPS`` into the generic fallback. This brain models that exact
    pathology so the loop-guard's behavior is locked in CI without a provider key.
    """

    def __init__(self, query: str = "leather wallet") -> None:
        self._query = query
        self.calls = 0

    def plan(self, history: list[Any], tool_results: list[str]) -> PlannerStep:
        self.calls += 1
        # Always the SAME tool call, regardless of accumulated tool_results — the bug.
        return PlannerStep(
            tool_calls=[ToolCall(name="search", args={"query": self._query})]
        )


def test_looping_planner_terminates_with_real_reply(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """A planner stuck re-issuing the identical search FORCES a grounded reply, not the
    generic fallback — and never exceeds the step budget (DEFECT-D22-01 loop-guard).

    Asserts: (1) the turn ends with a real grounded reply, NOT the
    ``"I wasn't able to finish that"`` dead-end; (2) the identical search ran exactly ONCE
    (the guard skips re-execution); (3) the planner was consulted at most twice — once to
    issue the call, once to detect the no-progress repeat — well under ``MAX_PLAN_STEPS``.
    """
    user = _user(seeded_db, handles, "buyer_primary")
    classifier = StubClassifier(IntentResult(route="shopping", confidence=0.9))
    planner = LoopingPlanner(query="wallet")
    with _session(seeded_db) as session:
        result = run_turn(
            session=session,
            user=user,
            text="show me a wallet",
            deps_overrides={"classifier": classifier, "planner": planner},
        )
        convo_id = result.conversation_id
        session.commit()
        # The identical search executed exactly once (audited) — the guard skips the repeat.
        searches = (
            session.scalar(
                select(func.count())
                .select_from(AgentAction)
                .where(
                    AgentAction.conversation_id == convo_id,
                    AgentAction.action_type == "search",
                )
            )
            or 0
        )

    # Terminates with a REAL reply, not the generic budget-exhausted apology.
    assert "I wasn't able to finish that" not in result.final_text
    assert result.final_text.strip() != ""
    assert "search" in result.final_text  # grounded in the actual tool result
    # The repeated call ran once, and the planner stalled in <= 2 steps (far under budget).
    assert searches == 1
    assert planner.calls <= 2
    assert planner.calls < MAX_PLAN_STEPS


# --------------------------------------------------------------------------- #
# Shopping → cart → checkout approval interrupt + resume.                      #
# --------------------------------------------------------------------------- #
def _checkout_planner(variant_id: str) -> StubPlanner:
    return StubPlanner(
        [
            PlannerStep(
                tool_calls=[ToolCall(name="addToCart", args={"variant_id": variant_id, "qty": 1})]
            ),
            PlannerStep(
                propose_checkout=True,
                checkout_summary="1x item — ready to place your order.",
            ),
        ]
    )


def test_checkout_interrupts_before_any_order(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """The graph MUST interrupt for approval before any order is placed — no order row."""
    user = _user(seeded_db, handles, "buyer_primary")
    variant_id = handles.variant_ids["mug_in_stock"]
    classifier = StubClassifier(IntentResult(route="shopping", confidence=0.9))
    graph = build_graph()
    with _session(seeded_db) as session:
        before = _order_count(session, user)
        result = run_turn(
            session=session,
            user=user,
            text="buy it",
            deps_overrides={"classifier": classifier, "planner": _checkout_planner(variant_id)},
            compiled_graph=graph,
        )
        session.commit()
        after = _order_count(session, user)

    assert result.awaiting_approval is True
    assert result.approval_payload is not None
    assert result.approval_payload["type"] == "checkout_approval"
    # HARD STOP: no order was placed at the interrupt.
    assert after == before


def test_resume_approved_places_order(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """Resume with approval → the real draftOrder runs and an order is placed."""
    user = _user(seeded_db, handles, "buyer_primary")
    variant_id = handles.variant_ids["mug_in_stock"]
    classifier = StubClassifier(IntentResult(route="shopping", confidence=0.9))
    graph = build_graph()
    with _session(seeded_db) as session:
        run = run_turn(
            session=session,
            user=user,
            text="buy it",
            deps_overrides={"classifier": classifier, "planner": _checkout_planner(variant_id)},
            compiled_graph=graph,
        )
        session.commit()
        assert run.awaiting_approval

        resumed = resume_turn(
            session=session,
            conversation_id=run.conversation_id,
            user=user,
            approved=True,
            compiled_graph=graph,
        )
        session.commit()
        order_count = session.scalar(
            select(func.count()).select_from(Order).where(Order.user_id == user.id)
        )

    assert not resumed.awaiting_approval
    assert resumed.action is not None
    assert resumed.action["action_type"] == "draftOrder"
    assert resumed.action["outcome"] == "applied"
    assert "order is placed" in resumed.final_text
    assert order_count == 1


def test_resume_rejected_places_no_order(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """Resume with rejection → no order, no side effect."""
    user = _user(seeded_db, handles, "buyer_primary")
    variant_id = handles.variant_ids["mug_in_stock"]
    classifier = StubClassifier(IntentResult(route="shopping", confidence=0.9))
    graph = build_graph()
    with _session(seeded_db) as session:
        run = run_turn(
            session=session,
            user=user,
            text="buy it",
            deps_overrides={"classifier": classifier, "planner": _checkout_planner(variant_id)},
            compiled_graph=graph,
        )
        session.commit()
        resumed = resume_turn(
            session=session,
            conversation_id=run.conversation_id,
            user=user,
            approved=False,
            compiled_graph=graph,
        )
        session.commit()
        order_count = session.scalar(
            select(func.count()).select_from(Order).where(Order.user_id == user.id)
        )

    assert not resumed.awaiting_approval
    assert resumed.action is None
    assert order_count == 0
