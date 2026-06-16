"""Agent conversation E2E — the journey-level shopping conversation (US-QA-D15).

WHAT THIS IS
============
A multi-turn AGENT CONVERSATION driven through Echo's real LangGraph runtime
(``app.agent.runner`` -> ``app.agent.graph``) against a real ``seeded_db``, exercising one
buyer's session end-to-end:

  1. SEARCH INTENT        — a discovery turn classifies to shopping + calls ``search``,
                            grounded on a real seeded product.
  2. PRODUCT COMPARISON   — a follow-up turn in the SAME conversation/``thread_id`` calls
                            ``productDetails`` on two seeded products (session continuity).
  3. ADD-TO-CART          — a turn calls ``addToCart``; the REAL cart line lands (verified
                            against the seeded DB via the Week-2 services/effects).
  4. CHECKOUT APPROVAL    — the shopping turn proposes checkout and the graph
                            ``interrupt()``s: NO order exists at the stop; resume(approved)
                            places the order (reserve/capture via the real ``draftOrder``);
                            a parallel conversation covers resume(reject) -> NO order.

Every turn is driven by a deterministic SCRIPTED brain (the ``brains`` injection seam) so
routing + tool selection are reproducible with NO provider key (CI-safe, the human's hard
requirement). Products/variants are resolved from the seed via the ``handles`` fixture
(anti-drift) — nothing is hand-seeded.

TOOL-CALL ACCURACY (acceptance requirement)
===========================================
The test EMITS a transcript artifact per run (``docs/qa/agent/agent-convo-<date>.{md,json}``
+ a stable ``-latest`` pointer, gitignored) capturing the conversation, each turn's tool
calls (name, args, outcome applied/refused), and a tool-call-accuracy measure: EXPECTED
tools (the scripted plan) vs ACTUAL tools called. "Actual" is read from the executor's own
``AgentAction`` audit rows — the authoritative record of what the runtime really ran — not
from the stub, so accuracy reflects the real execution path, not the script echoing itself.

LAYER SPLIT vs Echo's tests (deliberate, no overlap)
====================================================
Echo's ``tests/agent/test_orchestrator.py`` + ``test_agent_sse_e2e.py`` own the ATOMS:
per-node behavior, each route, the classifier/factory seam, the interrupt mechanics, the
SSE contract shape. This module does NOT re-assert any of those. It owns the JOURNEY-LEVEL
conversation invariants that only hold across a stitched multi-turn session:

  * session-state CONTINUITY — turns 2-4 reuse turn 1's ``conversation_id``/``thread_id``
    and the durable transcript accumulates user+assistant turns in order;
  * the add-to-cart EFFECT is real — a ``CartItem`` row for the resolved variant lands in
    the acting buyer's open cart with the right qty;
  * the approval gate is a HARD STOP at the journey level — across the whole conversation
    NO ``Order`` exists until an explicit approval, and the approve/reject fork diverges
    exactly there (one places an order, one does not);
  * REST and the agent see ONE catalog — the searched/compared/cart/ordered rows all
    resolve to the same seeded handles;
  * TOOL-CALL ACCURACY is logged end-to-end (expected-vs-actual over the real audit trail).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent import persistence
from app.agent.brains import IntentResult, PlannerStep, ToolCall
from app.agent.graph import build_graph
from app.agent.runner import resume_turn, run_turn
from app.db.models import AgentAction, Cart, CartItem, Order, User
from tests.conftest import ResolvedHandles, SeededDb
from tests.fixtures.handles import PERSONAS

# api/tests/agent/test_agent_convo_e2e.py -> parents[3] == repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_DIR = REPO_ROOT / "docs" / "qa" / "agent"


# --------------------------------------------------------------------------- #
# Scripted brains — deterministic, no LLM (the app.agent.brains injection seam). #
# --------------------------------------------------------------------------- #
class ScriptedClassifier:
    """Routes a turn to a fixed (route, confidence) verdict — no model."""

    def __init__(self, result: IntentResult) -> None:
        self._result = result

    def classify(self, history: list[Any]) -> IntentResult:
        return self._result


class ScriptedPlanner:
    """Replays a fixed sequence of PlannerSteps, one per ``plan`` call.

    A fresh planner is injected per turn (run-level state lives in the graph/DB, not the
    planner), so the step index is turn-local. The LAST step is sticky so an over-long
    plan loop degrades to the final reply rather than indexing past the script.
    """

    def __init__(self, steps: list[PlannerStep]) -> None:
        self._steps = list(steps)
        self._i = 0

    def plan(self, history: list[Any], tool_results: list[str]) -> PlannerStep:
        step = self._steps[min(self._i, len(self._steps) - 1)]
        self._i += 1
        return step


# --------------------------------------------------------------------------- #
# Transcript model — what each turn contributed, for the artifact + accuracy.   #
# --------------------------------------------------------------------------- #
@dataclass
class TurnRecord:
    """One conversation turn captured for the transcript artifact."""

    n: int
    label: str
    user_text: str
    assistant_text: str
    expected_tools: list[str]
    actual_tools: list[dict[str, str]]  # [{name, outcome}] from the audit trail
    awaiting_approval: bool
    note: str = ""


@dataclass
class Transcript:
    """The whole conversation + the tool-call-accuracy roll-up."""

    persona: str
    conversation_id: str
    turns: list[TurnRecord] = field(default_factory=list)

    # ---- tool-call accuracy: expected (script) vs actual (audit trail) ----
    def accuracy(self) -> dict[str, Any]:
        expected: list[str] = []
        actual: list[str] = []
        for t in self.turns:
            expected.extend(t.expected_tools)
            actual.extend(a["name"] for a in t.actual_tools)
        # Order-insensitive multiset match per the conversation as a whole.
        matched = _multiset_intersection(expected, actual)
        denom = max(len(expected), 1)
        return {
            "expected_tool_calls": expected,
            "actual_tool_calls": actual,
            "matched": matched,
            "expected_count": len(expected),
            "actual_count": len(actual),
            "matched_count": len(matched),
            "tool_call_accuracy": round(len(matched) / denom, 4),
        }


def _multiset_intersection(a: list[str], b: list[str]) -> list[str]:
    """Multiset ∩ preserving multiplicity (so a doubled expected tool needs two actuals)."""
    out: list[str] = []
    pool = list(b)
    for x in a:
        if x in pool:
            pool.remove(x)
            out.append(x)
    return out


# --------------------------------------------------------------------------- #
# Helpers — resolve seeded rows + read the real side effects / audit trail.     #
# --------------------------------------------------------------------------- #
def _user(seeded_db: SeededDb, handles: ResolvedHandles, persona: str) -> User:
    uid = handles.user_ids[PERSONAS[persona].handle]
    with Session(seeded_db.engine) as s:
        u = s.get(User, uid)
        assert u is not None
        return u


def _actions_for(session: Session, conversation_id: str) -> list[AgentAction]:
    """Every tool call the executor audited for this conversation, in order."""
    return list(
        session.scalars(
            select(AgentAction)
            .where(AgentAction.conversation_id == conversation_id)
            .order_by(AgentAction.created_at)
        )
    )


def _actual_tools_since(
    session: Session, conversation_id: str, already_seen: int
) -> tuple[list[dict[str, str]], int]:
    """The (name, outcome) of audited tool calls added since the last turn checkpoint.

    Returns the new tools plus the running total, so each turn records only the tools IT
    triggered (the audit trail is conversation-cumulative)."""
    rows = _actions_for(session, conversation_id)
    new = rows[already_seen:]
    tools = [{"name": r.action_type, "outcome": r.outcome} for r in new]
    return tools, len(rows)


def _order_count(session: Session, user: User) -> int:
    return (
        session.scalar(
            select(func.count()).select_from(Order).where(Order.user_id == user.id)
        )
        or 0
    )


def _open_cart_items(session: Session, user: User) -> list[CartItem]:
    cart = session.scalar(
        select(Cart).where(Cart.user_id == user.id, Cart.status == "open")
    )
    if cart is None:
        return []
    return list(
        session.scalars(select(CartItem).where(CartItem.cart_id == cart.id))
    )


# --------------------------------------------------------------------------- #
# The journey test.                                                            #
# --------------------------------------------------------------------------- #
def test_agent_conversation_journey_with_tool_call_accuracy(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """Drive search -> compare -> add-to-cart -> approved checkout in ONE conversation.

    Asserts the journey-level invariants (continuity, real cart effect, hard approval stop,
    one catalog) and writes the transcript + tool-call-accuracy artifact. A second short
    conversation covers the reject fork (no order). The whole thing runs on scripted brains
    with NO provider key.
    """
    user = _user(seeded_db, handles, "buyer_primary")
    mug = handles.product_ids["mug"]  # the canonical search/compare target
    wallet = handles.product_ids["card_wallet"]
    mug_variant = handles.variant_ids["mug_in_stock"]  # qty 24 — buyable

    classifier = ScriptedClassifier(IntentResult(route="shopping", confidence=0.92))

    # One compiled graph (with its MemorySaver checkpointer) threads the whole convo so the
    # checkout interrupt can resume on the SAME thread_id == conversation.id.
    graph = build_graph()

    transcript = Transcript(persona="buyer_primary", conversation_id="")
    seen_actions = 0

    with Session(seeded_db.engine) as session:
        # ---- baseline: clean slate for this buyer -------------------------------------
        assert _order_count(session, user) == 0
        assert _open_cart_items(session, user) == []

        # =============================== TURN 1: SEARCH ================================
        t1_tools = [ToolCall(name="search", args={"query": "pour over mug"})]
        planner = ScriptedPlanner(
            [
                PlannerStep(tool_calls=t1_tools),
                PlannerStep(reply="I found the Tide Pour-Over Mug — a sage ceramic pour-over."),
            ]
        )
        r1 = run_turn(
            session=session,
            user=user,
            text="show me a pour-over mug",
            deps_overrides={"classifier": classifier, "planner": planner},
            compiled_graph=graph,
        )
        session.commit()
        convo_id = r1.conversation_id
        transcript.conversation_id = convo_id
        actual1, seen_actions = _actual_tools_since(session, convo_id, seen_actions)
        transcript.turns.append(
            TurnRecord(
                n=1,
                label="search-intent",
                user_text="show me a pour-over mug",
                assistant_text=r1.final_text,
                expected_tools=[c.name for c in t1_tools],
                actual_tools=actual1,
                awaiting_approval=r1.awaiting_approval,
            )
        )
        # discovery turn: search actually ran (applied), grounded reply, no order/approval.
        assert not r1.awaiting_approval
        assert [a["name"] for a in actual1] == ["search"]
        assert actual1[0]["outcome"] == "applied"
        assert r1.final_text

        # ============================ TURN 2: COMPARISON ==============================
        # SAME conversation_id — session-state continuity across turns.
        t2_tools = [
            ToolCall(name="productDetails", args={"id_or_slug": mug}),
            ToolCall(name="productDetails", args={"id_or_slug": wallet}),
        ]
        planner = ScriptedPlanner(
            [
                PlannerStep(tool_calls=t2_tools),
                PlannerStep(
                    reply="The mug is a ceramic pour-over; the wallet is full-grain leather."
                ),
            ]
        )
        r2 = run_turn(
            session=session,
            user=user,
            text="how does it compare to the card wallet?",
            conversation_id=convo_id,
            deps_overrides={"classifier": classifier, "planner": planner},
            compiled_graph=graph,
        )
        session.commit()
        actual2, seen_actions = _actual_tools_since(session, convo_id, seen_actions)
        transcript.turns.append(
            TurnRecord(
                n=2,
                label="product-comparison",
                user_text="how does it compare to the card wallet?",
                assistant_text=r2.final_text,
                expected_tools=[c.name for c in t2_tools],
                actual_tools=actual2,
                awaiting_approval=r2.awaiting_approval,
                note="same thread_id as turn 1 (session continuity)",
            )
        )
        assert r2.conversation_id == convo_id  # continuity
        assert [a["name"] for a in actual2] == ["productDetails", "productDetails"]
        assert all(a["outcome"] == "applied" for a in actual2)

        # ============================= TURN 3: ADD-TO-CART ============================
        t3_tools = [ToolCall(name="addToCart", args={"variant_id": mug_variant, "qty": 2})]
        planner = ScriptedPlanner(
            [
                PlannerStep(tool_calls=t3_tools),
                PlannerStep(reply="Added 2 sage mugs to your cart."),
            ]
        )
        r3 = run_turn(
            session=session,
            user=user,
            text="add two of the sage mug to my cart",
            conversation_id=convo_id,
            deps_overrides={"classifier": classifier, "planner": planner},
            compiled_graph=graph,
        )
        session.commit()
        actual3, seen_actions = _actual_tools_since(session, convo_id, seen_actions)
        transcript.turns.append(
            TurnRecord(
                n=3,
                label="add-to-cart",
                user_text="add two of the sage mug to my cart",
                assistant_text=r3.final_text,
                expected_tools=[c.name for c in t3_tools],
                actual_tools=actual3,
                awaiting_approval=r3.awaiting_approval,
                note="real CartItem effect verified against seeded DB",
            )
        )
        assert [a["name"] for a in actual3] == ["addToCart"]
        assert actual3[0]["outcome"] == "applied"
        # REAL EFFECT: the cart line landed for the resolved seeded variant, right qty.
        items = _open_cart_items(session, user)
        assert len(items) == 1
        assert items[0].variant_id == mug_variant
        assert items[0].qty == 2

        # ====================== TURN 4: CHECKOUT APPROVAL STOP ========================
        # HARD STOP invariant across the whole journey: still NO order before approval.
        assert _order_count(session, user) == 0
        planner = ScriptedPlanner(
            [PlannerStep(propose_checkout=True, checkout_summary="2x Tide mug — place order?")]
        )
        r4 = run_turn(
            session=session,
            user=user,
            text="ok check me out",
            conversation_id=convo_id,
            deps_overrides={"classifier": classifier, "planner": planner},
            compiled_graph=graph,
        )
        session.commit()
        # checkout PROPOSAL emits no tool call (the draftOrder runs only after approval).
        actual4, seen_actions = _actual_tools_since(session, convo_id, seen_actions)
        transcript.turns.append(
            TurnRecord(
                n=4,
                label="checkout-approval-stop",
                user_text="ok check me out",
                assistant_text=r4.final_text or (r4.approval_payload or {}).get("summary", ""),
                expected_tools=[],  # interrupt fires BEFORE draftOrder
                actual_tools=actual4,
                awaiting_approval=r4.awaiting_approval,
                note="interrupt() hard-stops here; no order exists yet",
            )
        )
        assert r4.awaiting_approval is True
        assert r4.approval_payload is not None
        assert r4.approval_payload["type"] == "checkout_approval"
        assert actual4 == []  # no tool ran at the stop
        assert _order_count(session, user) == 0  # HARD STOP — nothing placed

        # ====================== TURN 4b: RESUME (APPROVED) ============================
        resumed = resume_turn(
            session=session,
            conversation_id=convo_id,
            user=user,
            approved=True,
            compiled_graph=graph,
        )
        session.commit()
        actual4b, seen_actions = _actual_tools_since(session, convo_id, seen_actions)
        transcript.turns.append(
            TurnRecord(
                n=5,
                label="checkout-resume-approved",
                user_text="<approve>",
                assistant_text=resumed.final_text,
                expected_tools=["draftOrder"],
                actual_tools=actual4b,
                awaiting_approval=resumed.awaiting_approval,
                note="explicit approval -> real draftOrder places the order",
            )
        )
        assert not resumed.awaiting_approval
        assert resumed.action is not None
        assert resumed.action["action_type"] == "draftOrder"
        assert resumed.action["outcome"] == "applied"
        assert [a["name"] for a in actual4b] == ["draftOrder"]
        assert _order_count(session, user) == 1  # order placed ONLY after approval

        # ---- session continuity: the durable transcript accumulated every turn -------
        convo = persistence.get_conversation(session, convo_id)
        assert convo is not None
        roles = [m.role for m in sorted(convo.messages, key=lambda m: m.created_at)]
        # 4 user turns + their assistant replies (the approval-paused turn 4 persisted its
        # assistant message only on resume), in strict alternation.
        assert roles.count("user") == 4
        assert roles.count("assistant") == 4

    # ----------------------- tool-call accuracy roll-up + write -----------------------
    accuracy = transcript.accuracy()
    # The journey was scripted to a 100%-accurate plan: every expected tool really ran.
    assert accuracy["tool_call_accuracy"] == 1.0, accuracy
    assert accuracy["actual_count"] == accuracy["expected_count"]

    _write_artifact(transcript, accuracy, reject_covered=True)


def test_checkout_reject_fork_places_no_order(
    seeded_db: SeededDb, handles: ResolvedHandles
) -> None:
    """The reject fork of the approval gate: resume(rejected) -> NO order, no side effect.

    The approve fork is covered in the main journey; this isolates the diverging branch so
    the hard-stop invariant is proven on BOTH outcomes from the same interrupt point.
    """
    user = _user(seeded_db, handles, "buyer_secondary")
    variant = handles.variant_ids["wallet_in_stock"]
    classifier = ScriptedClassifier(IntentResult(route="shopping", confidence=0.9))
    graph = build_graph()

    with Session(seeded_db.engine) as session:
        assert _order_count(session, user) == 0
        planner = ScriptedPlanner(
            [
                PlannerStep(
                    tool_calls=[ToolCall(name="addToCart", args={"variant_id": variant, "qty": 1})]
                ),
                PlannerStep(propose_checkout=True, checkout_summary="1x wallet — place order?"),
            ]
        )
        run = run_turn(
            session=session,
            user=user,
            text="buy the tan wallet",
            deps_overrides={"classifier": classifier, "planner": planner},
            compiled_graph=graph,
        )
        session.commit()
        assert run.awaiting_approval
        assert _order_count(session, user) == 0  # hard stop

        rejected = resume_turn(
            session=session,
            conversation_id=run.conversation_id,
            user=user,
            approved=False,
            compiled_graph=graph,
        )
        session.commit()

    assert not rejected.awaiting_approval
    assert rejected.action is None
    assert _order_count(session, user) == 0  # reject -> nothing placed


# --------------------------------------------------------------------------- #
# Artifact emission — follows the retrieval-smoke / regression convention.      #
# --------------------------------------------------------------------------- #
def _write_artifact(
    transcript: Transcript, accuracy: dict[str, Any], *, reject_covered: bool
) -> None:
    """Write ``agent-convo-<date>.{json,md}`` + ``-latest`` pointers (gitignored)."""
    stamp = datetime.now(UTC)
    payload: dict[str, Any] = {
        "generated_at": stamp.isoformat(),
        "story": "US-QA-D15",
        "kind": "agent-conversation-e2e",
        "driver": "app.agent.runner (real LangGraph runtime, scripted brains, no provider key)",
        "persona": transcript.persona,
        "conversation_id": transcript.conversation_id,
        "reject_fork_covered": reject_covered,
        "tool_call_accuracy": accuracy["tool_call_accuracy"],
        "tool_call_summary": {
            "expected_count": accuracy["expected_count"],
            "actual_count": accuracy["actual_count"],
            "matched_count": accuracy["matched_count"],
        },
        "turns": [
            {
                "n": t.n,
                "label": t.label,
                "user": t.user_text,
                "assistant": t.assistant_text,
                "expected_tools": t.expected_tools,
                "actual_tools": t.actual_tools,
                "awaiting_approval": t.awaiting_approval,
                "note": t.note,
            }
            for t in transcript.turns
        ],
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    date = stamp.strftime("%Y-%m-%d")
    (ARTIFACT_DIR / f"agent-convo-{date}.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    (ARTIFACT_DIR / "agent-convo-latest.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )

    md = _render_md(payload)
    (ARTIFACT_DIR / f"agent-convo-{date}.md").write_text(md, encoding="utf-8")
    (ARTIFACT_DIR / "agent-convo-latest.md").write_text(md, encoding="utf-8")

    print("\n=== Agent conversation E2E — US-QA-D15 ===")
    print(
        f"persona={payload['persona']}  convo={payload['conversation_id']}  "
        f"turns={len(payload['turns'])}"
    )
    print(
        f"tool-call accuracy={accuracy['tool_call_accuracy']:.3f} "
        f"(matched {accuracy['matched_count']}/{accuracy['expected_count']} expected; "
        f"actual={accuracy['actual_count']})"
    )
    print(f"artifact -> {(ARTIFACT_DIR / f'agent-convo-{date}.json').relative_to(REPO_ROOT)}")


def _render_md(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Agent conversation E2E — transcript (US-QA-D15)\n")
    lines.append(f"- Generated: `{payload['generated_at']}`")
    lines.append(f"- Persona: `{payload['persona']}`")
    lines.append(f"- Conversation: `{payload['conversation_id']}`")
    lines.append(f"- Driver: {payload['driver']}")
    acc = payload["tool_call_accuracy"]
    s = payload["tool_call_summary"]
    lines.append(
        f"- **Tool-call accuracy: {acc:.3f}** "
        f"(matched {s['matched_count']}/{s['expected_count']} expected; "
        f"actual={s['actual_count']})"
    )
    lines.append(f"- Reject fork covered: {payload['reject_fork_covered']}\n")
    lines.append("## Turns\n")
    lines.append("| # | label | user | tools (expected -> actual) | approval |")
    lines.append("| - | --- | --- | --- | --- |")
    for t in payload["turns"]:
        exp = ", ".join(t["expected_tools"]) or "—"
        act = ", ".join(f"{a['name']}({a['outcome']})" for a in t["actual_tools"]) or "—"
        user_text = t["user"].replace("|", "\\|")
        lines.append(
            f"| {t['n']} | {t['label']} | {user_text} | {exp} -> {act} | "
            f"{'yes' if t['awaiting_approval'] else 'no'} |"
        )
    lines.append("\n## Assistant replies\n")
    for t in payload["turns"]:
        assistant = t["assistant"].replace("\n", " ")
        lines.append(f"- **Turn {t['n']} ({t['label']})**: {assistant}")
        if t["note"]:
            lines.append(f"  - _{t['note']}_")
    return "\n".join(lines) + "\n"


__all__: list[str] = []
