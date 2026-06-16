"""The orchestrator graph — LangGraph StateGraph (US-E5-03/04, ADR-0031).

A single ``StateGraph`` is the product's agent runtime:

    classify ──low-confidence──▶ clarify ─▶ END
       │ (route)
       ├─ shopping ─▶ (plan-execute loop) ─▶ [interrupt: approve checkout] ─▶ checkout ─▶ END
       ├─ support  ─▶ deferred ("not available yet") ─▶ END   (built Day 16)
       └─ merch    ─▶ deferred ("not available yet") ─▶ END   (built Day 17)

ROUTING POLICY (human-ratified, ADR-0031):
  * An LLM intent-classification node (``classify``) routes to shopping | support |
    merchandising via structured output.
  * AMBIGUITY FALLBACK: when confidence < ``CLARIFY_THRESHOLD`` the router does NOT guess
    and does NOT dead-end — it routes to the shopping agent with ONE clarifying turn.
  * support / merchandising are REGISTERED nodes that return a graceful "not available
    yet" assistant message (never a 501/crash).

HUMAN-IN-THE-LOOP (human-ratified): before ANY order placement or payment, the shopping
flow calls LangGraph ``interrupt()`` and surfaces the checkout plan. The graph pauses;
only an explicit approval (resume with ``Command(resume=...)``) runs the ``checkout`` node
that places the order via the real ``draftOrder`` tool. A rejection ends the turn with no
side effect.

SESSION STATE: the graph is compiled with a checkpointer keyed on ``thread_id`` (==
``conversation.id``) so an interrupted turn resumes. The DURABLE record of turns lives in
our ``conversations``/``messages``/``agent_actions`` tables (``persistence.py`` +
executor audit) — the checkpointer is in-graph thread state only.

The chat model / brains are INJECTABLE (``GraphDeps``) so CI runs with a fake brain and no
provider key. The session + acting user + conversation id are injected per run via the
graph config (``configurable``), never taken from the LLM.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt
from sqlalchemy.orm import Session, sessionmaker
from typing_extensions import TypedDict

from app.agent.brains import (
    IntentClassifier,
    IntentResult,
    LLMIntentClassifier,
    LLMMerchBrain,
    LLMShoppingPlanner,
    LLMSupportBrain,
    MerchBrain,
    PlannerStep,
    ShoppingPlanner,
    SupportBrain,
    SupportPlan,
)
from app.agent.cache import (
    CacheNodeType,
    cache_lookup,
    cache_store,
    runtime_cache_key,
)
from app.agent.executor import execute_tool
from app.agent.guardrails import (
    INJECTION_REFUSAL,
    InjectionHit,
    scan_for_injection,
)
from app.agent.merch import (
    generate_merch_draft,
    generate_merch_draft_async,
    policy_content_version,
)
from app.agent.tools import DraftOrderInput, OrderStatusInput, RefundInput, ToolName
from app.agent.trace import node_span, set_route
from app.core.errors import APIError
from app.db.models import User
from app.schemas.agent import MerchDraftOut
from app.schemas.enums import AgentOutcome
from app.services import rag

# Below this classifier confidence, route to shopping with one clarifying turn instead of
# committing to a guessed route (human-ratified ambiguity fallback).
CLARIFY_THRESHOLD = 0.55

# Bound the plan-execute tool loop so a misbehaving planner can't spin forever.
MAX_PLAN_STEPS = 6


class AgentState(TypedDict, total=False):
    """The graph's working state for one turn (checkpointed per thread_id)."""

    messages: Annotated[list[BaseMessage], add_messages]
    route: str
    confidence: float
    clarifying: bool
    # The checkout plan surfaced for approval + the resume decision.
    checkout_summary: str
    ship_address: dict[str, Any]
    approved: bool
    # The final assistant text + the action this turn produced.
    final_text: str
    action: dict[str, Any] | None
    # Grounding citations for the turn (support RAG). Each is a serialized Citation.
    citations: list[dict[str, Any]]


@dataclass
class GraphDeps:
    """Everything a run needs that is NOT serializable graph state.

    Injected per run via the graph's ``configurable`` so tests can pass a stub brain and
    CI needs no provider key. ``session``/``user``/``conversation_id`` come from the
    request context (resolved via ``app.api.deps``), NEVER from the model.
    """

    session: Session
    user: User
    conversation_id: str | None = None
    classifier: IntentClassifier | None = None
    planner: ShoppingPlanner | None = None
    support: SupportBrain | None = None
    merch: MerchBrain | None = None
    # Store scope for the support policy cache (the buyer's active store context, if any) —
    # None = platform/global policies only. NEVER read from model output.
    support_store_id: str | None = None
    # The seller's store for merchandising (resolved from request context, never the model).
    seller_store_id: str | None = None
    # Session factory for OFF-critical-path work (async merch generation commits on its own
    # session/thread). None -> the merch node falls back to the request session (tests).
    session_factory: sessionmaker[Session] | None = None
    # Default ship address for the checkout step when the turn didn't supply one.
    default_ship_address: dict[str, Any] = field(
        default_factory=lambda: {
            "recipient_name": "Shopper",
            "line1": "1 Market St",
            "city": "Springfield",
            "postal_code": "00000",
            "country": "US",
        }
    )


def _deps(config: dict[str, Any]) -> GraphDeps:
    deps = config.get("configurable", {}).get("deps")
    if not isinstance(deps, GraphDeps):  # pragma: no cover - misconfiguration guard
        raise RuntimeError("GraphDeps must be provided via config['configurable']['deps'].")
    return deps


# --------------------------------------------------------------------------- #
# Nodes.                                                                        #
# --------------------------------------------------------------------------- #
def _classify_node(state: AgentState, config: dict[str, Any]) -> dict[str, Any]:
    """LLM intent classification -> route + confidence (the routing decision).

    Semantic-cached (ADR-0034 §2): intent classification is the every-turn, non-personalized
    win (raw utterance + fixed system prompt, no identity/PII). ORDERING is load-bearing
    (ADR-0033): scan_for_injection -> cache lookup -> brain -> cache store. The cache NEVER
    sits ahead of the injection scan; an injection-fired turn is never cached (it routes on
    so the downstream node refuses + logs it).
    """
    deps = _deps(config)
    history = list(state["messages"])
    user_text = _latest_user_text(history)

    injected = scan_for_injection(user_text) is not None
    use_cache = bool(user_text) and not injected
    key = runtime_cache_key(CacheNodeType.classify)

    if use_cache:
        cached = cache_lookup(deps.session, key=key, prompt=user_text)
        if cached is not None:
            return _classify_result(IntentResult.model_validate(cached))

    classifier = deps.classifier or LLMIntentClassifier(_require_model(config))
    result = classifier.classify(history)

    # Store ONLY a clean classification (never an injection-fired turn). A lookup/store
    # failure degrades to the live result — it never surfaces as an error.
    if use_cache:
        cache_store(
            deps.session, key=key, prompt=user_text, response=result.model_dump(mode="json")
        )
    return _classify_result(result)


def _classify_result(result: IntentResult) -> dict[str, Any]:
    clarifying = result.confidence < CLARIFY_THRESHOLD
    # Ambiguity fallback: low confidence -> shopping agent with a clarifying turn.
    route = "shopping" if clarifying else result.route
    set_route(route)  # observability (best-effort): record the routing decision.
    return {"route": route, "confidence": result.confidence, "clarifying": clarifying}


def _route_after_classify(
    state: AgentState,
) -> Literal["clarify", "shopping", "support", "merchandising"]:
    if state.get("clarifying"):
        return "clarify"
    route = state.get("route", "shopping")
    if route in ("shopping", "support", "merchandising"):
        return route  # type: ignore[return-value]
    return "shopping"


def _clarify_node(state: AgentState, config: dict[str, Any]) -> dict[str, Any]:
    """Ambiguous turn: ask ONE clarifying question (shopping-agent owned). No guess."""
    text = (
        "I want to make sure I help with the right thing — are you looking to shop for "
        "a product, check on an order, or something else? Tell me a bit more and I'll "
        "jump in."
    )
    return {
        "final_text": text,
        "messages": [AIMessage(content=text)],
        "action": None,
    }


def _tool_call_signature(name: str, args: dict[str, Any]) -> str:
    """A normalized, order-independent key for a tool call (name + canonical args).

    The loop-guard tracks calls by this signature so an IDENTICAL re-issued call (same
    tool, same args, regardless of dict insertion order) is recognized as a repeat and is
    NOT re-executed — the provider-agnostic defense against DEFECT-D22-01 where the live
    planner re-emits the same ``search(...)`` every step.
    """
    try:
        canonical = json.dumps(args, sort_keys=True, default=str)
    except (TypeError, ValueError):  # pragma: no cover - defensive: unhashable arg shapes
        canonical = repr(sorted(args.items()))
    return f"{name}:{canonical}"


def _synthesize_reply(tool_results: list[str]) -> str:
    """A grounded fallback reply built from EXISTING tool results when the planner stalls.

    DEFECT-D22-01: a misbehaving planner that keeps re-issuing the same call (never
    flipping to ``reply``) used to exhaust the step budget and hit the generic graceful
    fallback. With the loop-guard we instead FORCE a reply from what we already retrieved,
    so the turn terminates with real, grounded content rather than a dead-end apology.
    """
    if not tool_results:
        return "Let me know what you'd like to do next."
    return (
        "Here's what I found for you:\n"
        + "\n".join(tool_results)
        + "\nLet me know if you'd like details on any of these or want to add one to your cart."
    )


def _shopping_node(state: AgentState, config: dict[str, Any]) -> dict[str, Any]:
    """Plan-execute shopping turn: discovery/cart tools, then either reply or propose
    checkout (which leads to the approval interrupt). Order placement is NOT done here.

    LOOP-GUARD (DEFECT-D22-01, ADR-0042 §D2 — provider-agnostic). The live planner can
    re-issue the IDENTICAL tool call every step without ever flipping to ``reply``. To stop
    that burning the whole step budget into the generic fallback we:
      * track each issued call by its normalized signature;
      * never RE-EXECUTE an identical call (it would just waste a step + repeat the result);
      * once ``tool_results`` exist and a step makes NO PROGRESS (issues only repeats, or
        issues no new tool call and doesn't reply/propose), FORCE a grounded reply
        synthesized from the results we already have.
    Legitimate multi-tool and checkout-proposal paths are untouched — only a stalled,
    repeating planner is short-circuited."""
    deps = _deps(config)
    history = list(state["messages"])

    # Guardrail: a user turn cannot re-instruct the agent (ADR-0033 §2). Detect-log-refuse.
    hit = scan_for_injection(_latest_user_text(history))
    if hit is not None:
        _log_injection(deps, hit)
        return _refusal_result(INJECTION_REFUSAL, reason="prompt_injection", name="guardrail")

    planner = deps.planner or LLMShoppingPlanner(_require_model(config))
    tool_results: list[str] = []
    seen_calls: set[str] = set()

    for _ in range(MAX_PLAN_STEPS):
        step: PlannerStep = planner.plan(history, tool_results)
        if step.tool_calls:
            # Run only NOT-yet-seen calls; an identical re-issue is skipped (no wasted step
            # re-running it). If every call this step is a repeat, the planner made no
            # progress — and once we already have results, force a grounded reply instead
            # of looping toward the budget exhaustion / generic fallback.
            new_calls = [
                call
                for call in step.tool_calls
                if _tool_call_signature(call.name, dict(call.args)) not in seen_calls
            ]
            if not new_calls and tool_results:
                text = _synthesize_reply(tool_results)
                return {
                    "final_text": text,
                    "messages": [AIMessage(content=text)],
                    "action": None,
                }
            for call in new_calls:
                seen_calls.add(_tool_call_signature(call.name, dict(call.args)))
                tool_results.append(_run_shopping_tool(deps, call.name, dict(call.args)))
            # Either ran new calls, or repeated calls with no results yet — plan again.
            continue
        if step.propose_checkout:
            return {
                "checkout_summary": step.checkout_summary or "Place your order?",
                "route": "shopping",
            }
        text = step.reply or "Let me know what you'd like to do next."
        return {
            "final_text": text,
            "messages": [AIMessage(content=text)],
            "action": None,
        }

    # Step budget exhausted. If we gathered results along the way, terminate with a grounded
    # reply (DEFECT-D22-01); only a wholly empty run falls back to the generic apology.
    if tool_results:
        text = _synthesize_reply(tool_results)
    else:
        text = "I wasn't able to finish that — could you rephrase what you're after?"
    return {"final_text": text, "messages": [AIMessage(content=text)], "action": None}


def _route_after_shopping(state: AgentState) -> Literal["approve_checkout", "__end__"]:
    """If the shopping node proposed a checkout, go to the approval gate; else end."""
    return "approve_checkout" if state.get("checkout_summary") else END  # type: ignore[return-value]


def _approve_checkout_node(state: AgentState, config: dict[str, Any]) -> dict[str, Any]:
    """HARD approval stop: interrupt the graph and surface the checkout plan.

    ``interrupt()`` pauses the run BEFORE any order is placed. The graph is resumed with
    ``Command(resume={"approved": bool, "ship_address": {...}?})``. Only ``approved: True``
    proceeds to the ``checkout`` node; anything else ends the turn with no side effect.
    """
    decision = interrupt(
        {
            "type": "checkout_approval",
            "summary": state.get("checkout_summary", ""),
            "message": "Approve to place this order. Nothing is charged until you approve.",
        }
    )
    approved = bool(decision.get("approved")) if isinstance(decision, dict) else bool(decision)
    ship = decision.get("ship_address") if isinstance(decision, dict) else None
    out: dict[str, Any] = {"approved": approved}
    if isinstance(ship, dict):
        out["ship_address"] = ship
    return out


def _route_after_approval(state: AgentState) -> Literal["checkout", "__end__"]:
    return "checkout" if state.get("approved") else END  # type: ignore[return-value]


def _checkout_node(state: AgentState, config: dict[str, Any]) -> dict[str, Any]:
    """Approved: place the order via the real ``draftOrder`` tool (executor-audited)."""
    deps = _deps(config)
    ship = state.get("ship_address") or deps.default_ship_address
    try:
        result = execute_tool(
            ToolName.draft_order,
            DraftOrderInput(ship_address=ship).model_dump(mode="json"),
            session=deps.session,
            user=deps.user,
            conversation_id=deps.conversation_id,
        )
    except APIError as exc:
        text = f"I couldn't place the order: {exc.message}"
        return {
            "final_text": text,
            "messages": [AIMessage(content=text)],
            "action": {"action_type": ToolName.draft_order.value, "outcome": "refused"},
        }
    payload = result.output.model_dump(mode="json")
    order = payload.get("order", {})
    text = (
        f"Your order is placed (order {order.get('order_number', order.get('id', ''))}). "
        "A payment intent is ready for confirmation."
    )
    return {
        "final_text": text,
        "messages": [AIMessage(content=text)],
        "action": {
            "action_type": ToolName.draft_order.value,
            "outcome": "applied",
            "payload": payload,
        },
    }


# --------------------------------------------------------------------------- #
# Support agent (US-E5-06): policy RAG + order status + refunds (HITL tiered).  #
# --------------------------------------------------------------------------- #
def _latest_user_text(history: list[BaseMessage]) -> str:
    for msg in reversed(history):
        if isinstance(msg, HumanMessage):
            return str(msg.content)
    return ""


def _reply(text: str, *, action: dict[str, Any] | None = None) -> dict[str, Any]:
    """A plain assistant reply (no citations, optional action)."""
    return {
        "final_text": text,
        "messages": [AIMessage(content=text)],
        "action": action,
        "citations": [],
    }


def _refusal_result(text: str, *, reason: str, name: str) -> dict[str, Any]:
    """Terminal refusal: surface a safe message + a refused action for the audit trail."""
    return _reply(
        text,
        action={
            "action_type": name,
            "outcome": AgentOutcome.refused.value,
            "reason": reason,
        },
    )


def _log_injection(deps: GraphDeps, hit: InjectionHit) -> None:
    """Record a detected injection attempt as a refused ``agent_actions`` row (signal)."""
    from app.db.models import AgentAction

    deps.session.add(
        AgentAction(
            conversation_id=deps.conversation_id,
            actor_user_id=deps.user.id,
            action_type="guardrail",
            payload={"kind": hit.kind.value, "span": hit.span, "reason": "prompt_injection"},
            outcome=AgentOutcome.refused.value,
        )
    )
    deps.session.flush()


def _support_node(state: AgentState, config: dict[str, Any]) -> dict[str, Any]:
    """Support turn: ground policy answers (RAG), report order status, handle refunds.

    Guardrail-first: the latest user turn is scanned for prompt injection BEFORE anything
    else; a hit is logged + refused (ADR-0033 §2). Retrieved policy passages are also
    scanned (untrusted content) before they ground an answer. Refunds run through the
    executor, which applies the HITL tier (ADR-0033 §1) — the node never decides the tier.
    """
    deps = _deps(config)
    history = list(state["messages"])
    user_text = _latest_user_text(history)

    # Guardrail: untrusted USER content cannot re-instruct the agent.
    hit = scan_for_injection(user_text)
    if hit is not None:
        _log_injection(deps, hit)
        return _refusal_result(INJECTION_REFUSAL, reason="prompt_injection", name="guardrail")

    brain: SupportBrain = deps.support or LLMSupportBrain(_require_model(config))
    plan: SupportPlan = brain.plan(history)

    if plan.intent == "order_status":
        return _support_order_status(deps, plan)
    if plan.intent == "refund":
        return _support_refund(deps, plan)
    return _support_policy(deps, plan, user_text)


def _support_policy(deps: GraphDeps, plan: SupportPlan, user_text: str) -> dict[str, Any]:
    """Answer a policy question grounded in retrieved policy docs; refuse if ungrounded.

    Semantic-cached (ADR-0034 §2), STORE-SCOPED: a grounded policy answer is tenant-shared,
    non-personalized, so it's cacheable per store. The user-turn injection scan already ran
    in ``_support_node`` (cache sits BEHIND it — ADR-0033). Invalidation: the cache key folds
    ``store_id`` and the entry carries a ``content_version`` = the in-scope policies' version
    snapshot, so a policy EDIT busts stale answers before TTL (1h backstop). A refusal /
    ungrounded turn is NEVER cached.
    """
    query = plan.query or user_text
    store_id = deps.support_store_id
    key = runtime_cache_key(CacheNodeType.policy, store_id=store_id)
    version = policy_content_version(deps.session, store_id=store_id)

    cached = cache_lookup(deps.session, key=key, prompt=query, content_version=version)
    if cached is not None:
        text = str(cached.get("answer", ""))
        return {
            "final_text": text,
            "messages": [AIMessage(content=text)],
            "action": None,
            "citations": list(cached.get("citations", [])),
        }

    docs = rag.retrieve_policies(deps.session, query=query, store_id=store_id, limit=4)

    # Guardrail: retrieved passages are untrusted data — scan before grounding on them.
    hit = scan_for_injection(*(d.text for d in docs))
    if hit is not None:
        _log_injection(deps, hit)
        return _refusal_result(INJECTION_REFUSAL, reason="prompt_injection", name="guardrail")

    if not docs:
        text = (
            "I couldn't find a policy that answers that. I won't guess — please rephrase, "
            "or reach out to support and a person can help."
        )
        return _refusal_result(text, reason="no_grounding", name="support_policy")

    # Ground the answer in the retrieved policy prose (faithful by construction: the answer
    # IS the cited policy text). A live LLM would phrase this; the grounded content + the
    # citations are what the faithfulness/recall gate checks.
    top = docs[0]
    answer = top.text.split("\n", 1)[-1].strip() if "\n" in top.text else top.text.strip()
    citations = _citations(docs)

    # Cache the grounded success only (never a refusal). source_ids + the version snapshot
    # drive content-version invalidation; a store-edit bumps the snapshot and busts this.
    cache_store(
        deps.session,
        key=key,
        prompt=query,
        response={"answer": answer, "citations": citations},
        source_ids=[d.source_id for d in docs],
        content_version=version,
    )
    return {
        "final_text": answer,
        "messages": [AIMessage(content=answer)],
        "action": None,
        "citations": citations,
    }


def _support_order_status(deps: GraphDeps, plan: SupportPlan) -> dict[str, Any]:
    """Report an order's status via the orderStatus tool (owner-scoped in the service)."""
    if not plan.order_id:
        return _reply("Which order would you like the status for? Share the order id.")
    try:
        result = execute_tool(
            ToolName.order_status,
            OrderStatusInput(order_id=plan.order_id).model_dump(mode="json"),
            session=deps.session,
            user=deps.user,
            conversation_id=deps.conversation_id,
        )
    except APIError as exc:
        text = f"I couldn't look that order up: {exc.message}"
        return _refusal_result(text, reason=exc.code.value, name=ToolName.order_status.value)
    payload = result.output.model_dump(mode="json")
    status = payload.get("status", "unknown")
    number = payload.get("order_number", payload.get("id", plan.order_id))
    text = f"Order {number} is currently '{status}'."
    return {
        "final_text": text,
        "messages": [AIMessage(content=text)],
        "action": {
            "action_type": ToolName.order_status.value,
            "outcome": AgentOutcome.applied.value,
            "payload": payload,
        },
        "citations": [],
    }


def _support_refund(deps: GraphDeps, plan: SupportPlan) -> dict[str, Any]:
    """Request a refund; the executor applies the HITL tier (auto/hitl_deferred/refuse)."""
    if not plan.order_id:
        return _reply("I can help with a refund — which order is it? Share the order id.")
    try:
        result = execute_tool(
            ToolName.refund,
            RefundInput(order_id=plan.order_id, reason=plan.reason or None).model_dump(mode="json"),
            session=deps.session,
            user=deps.user,
            conversation_id=deps.conversation_id,
        )
    except APIError as exc:
        # Includes the >$200 hard-refuse (forbidden) tier and not-found/conflict.
        text = f"I couldn't process that refund: {exc.message}"
        return _refusal_result(text, reason=exc.code.value, name=ToolName.refund.value)

    payload = result.output.model_dump(mode="json")
    if result.outcome == AgentOutcome.hitl_deferred:
        text = (
            "I've queued this refund for a human on the support team to review — it's "
            "above the amount I can approve on my own. You'll hear back once it's handled."
        )
        outcome = AgentOutcome.hitl_deferred.value
    else:
        text = "Done — I've refunded that order to your original payment method."
        outcome = AgentOutcome.applied.value
    return {
        "final_text": text,
        "messages": [AIMessage(content=text)],
        "action": {
            "action_type": ToolName.refund.value,
            "outcome": outcome,
            "payload": payload,
        },
        "citations": [],
    }


def _citations(docs: list[rag.RetrievedDoc]) -> list[dict[str, Any]]:
    """Serialize retrieved docs into the contract Citation shape for the SSE frame."""
    from app.schemas.agent import Citation

    out: list[dict[str, Any]] = []
    for doc in docs:
        citation = Citation(
            source_type=doc.source_type,  # type: ignore[arg-type]
            source_id=doc.source_id,
            chunk_index=doc.chunk_index,
            snippet=doc.snippet(),
            score=doc.score,
        )
        data = citation.model_dump(mode="json")
        # Carry the golden source key so Juno's RAGAS can resolve a live citation back to
        # the golden ``source_docs`` expectation (kind@store / slug).
        data["citation_key"] = doc.citation_key
        out.append(data)
    return out


# --------------------------------------------------------------------------- #
# Merchandising agent (US-E5-08): draft listing + comparables price suggestion. #
# --------------------------------------------------------------------------- #
def _merchandising_node(state: AgentState, config: dict[str, Any]) -> dict[str, Any]:
    """Seller merchandising turn: generate a DRAFT listing + comparables price suggestion.

    Guardrail-first (ADR-0034 §3): the seller's brief is scanned for injection BEFORE
    generation; the retrieved comparables are scanned by the brain path too. Identity/scope
    (the seller's store) comes from request context (``deps.seller_store_id`` resolved via
    ``require_user``), never from model output. Generation runs OFF the request's
    critical-path session (a fresh worker session that commits independently — the async
    seam); the turn returns the completed DRAFT. The draft is NEVER published.
    """
    deps = _deps(config)
    history = list(state["messages"])
    brief = _latest_user_text(history)

    hit = scan_for_injection(brief)
    if hit is not None:
        _log_injection(deps, hit)
        return _refusal_result(INJECTION_REFUSAL, reason="prompt_injection", name="guardrail")

    if not deps.seller_store_id:
        text = (
            "I can help you draft a listing, but I couldn't tell which store this is for. "
            "Open this from your seller dashboard and I'll prepare a draft."
        )
        return _reply(text)

    brain: MerchBrain = deps.merch or LLMMerchBrain(_require_model(config))
    draft = _run_merch_generation(deps, brief=brief, brain=brain)

    text = (
        f"I've prepared a draft listing “{draft.title}” with a suggested price "
        f"of {(draft.price_suggestion.suggested_price_minor or 0) / 100:.2f}. "
        f"{draft.price_suggestion.basis} It's saved as a draft for you to review and "
        "publish — nothing is live yet."
    )
    return {
        "final_text": text,
        "messages": [AIMessage(content=text)],
        "action": {
            "action_type": "merch_draft",
            "outcome": AgentOutcome.applied.value,
            "payload": draft.model_dump(mode="json"),
        },
        "citations": [],
    }


def _run_merch_generation(
    deps: GraphDeps, *, brief: str, brain: MerchBrain
) -> MerchDraftOut:
    """Run draft generation off the request critical path, return the completed draft.

    Prefers an injected ``session_factory`` so generation commits on its OWN session/thread
    (the async seam, ADR-0034 §3 — draft retrievable once ready). Falls back to the request
    session (e.g. a test driving the node directly without a factory) so the path is always
    exercisable. Either way the brain only writes copy; price is computed structurally; the
    draft persists with ``status='draft'`` and is never published.
    """
    if deps.session_factory is not None:
        future = generate_merch_draft_async(
            deps.session_factory,
            brief=brief,
            store_id=deps.seller_store_id or "",
            brain=brain,
        )
        return future.result()
    return generate_merch_draft(
        deps.session, brief=brief, store_id=deps.seller_store_id or "", brain=brain
    )


# --------------------------------------------------------------------------- #
# Shopping tool runner (thin — reuses the executor; tools also wrapped for the  #
# planner via langchain_tools, this path is the graph driving them directly).   #
# --------------------------------------------------------------------------- #
def _run_shopping_tool(deps: GraphDeps, name: str, args: dict[str, Any]) -> str:
    """Run one discovery/cart tool via the executor; return a compact result string.

    Refuses to run order-placing/sensitive tools from the autonomous loop — those go
    through the approval gate (draftOrder) or the support agent (refund).
    """
    if name in (ToolName.draft_order.value, ToolName.refund.value):
        return f"{name}: blocked — order placement requires approval."
    try:
        result = execute_tool(
            name,
            args,
            session=deps.session,
            user=deps.user,
            conversation_id=deps.conversation_id,
        )
    except APIError as exc:
        return f"{name} error[{exc.code.value}]: {exc.message}"
    return f"{name}: {result.output.model_dump(mode='json')}"


def _require_model(config: dict[str, Any]) -> Any:
    """Resolve the chat model for a default (non-injected) brain. Lazy so CI never
    constructs a provider client when a stub brain is injected."""
    deps = _deps(config)
    model = config.get("configurable", {}).get("model")
    if model is not None:
        return model
    from app.agent.llm import get_chat_model

    _ = deps
    return get_chat_model()


# --------------------------------------------------------------------------- #
# Graph assembly.                                                              #
# --------------------------------------------------------------------------- #
def build_graph(checkpointer: BaseCheckpointSaver[Any] | None = None) -> Any:
    """Compile the orchestrator graph. Pass a checkpointer (default: in-memory).

    The checkpointer is REQUIRED for the ``interrupt()`` approval gate to resume across
    invocations; ``MemorySaver`` is fine for a single process / tests. Production wires a
    durable checkpointer keyed on ``thread_id`` == ``conversation.id``.
    """
    g: StateGraph = StateGraph(AgentState)

    # Nodes take (state, config); langgraph adapts the 2-arg signature at runtime but its
    # type stub only models the single-arg form, so cast through a local adder. Every node
    # is wrapped in a ``node_span`` so the trace records per-node latency (best-effort, a
    # no-op outside a traced turn) without touching each node body (US-E7-04, ADR-0042 §D1).
    def _add(name: str, fn: Callable[[AgentState, dict[str, Any]], dict[str, Any]]) -> None:
        def _traced(state: AgentState, config: dict[str, Any]) -> dict[str, Any]:
            with node_span(name):
                return fn(state, config)

        g.add_node(name, cast("Callable[[Any], Any]", _traced))

    _add("classify", _classify_node)
    _add("clarify", _clarify_node)
    _add("shopping", _shopping_node)
    _add("approve_checkout", _approve_checkout_node)
    _add("checkout", _checkout_node)
    _add("support", _support_node)
    _add("merchandising", _merchandising_node)

    g.add_edge(START, "classify")
    g.add_conditional_edges(
        "classify",
        _route_after_classify,
        {
            "clarify": "clarify",
            "shopping": "shopping",
            "support": "support",
            "merchandising": "merchandising",
        },
    )
    g.add_conditional_edges(
        "shopping",
        _route_after_shopping,
        {"approve_checkout": "approve_checkout", END: END},
    )
    g.add_conditional_edges(
        "approve_checkout",
        _route_after_approval,
        {"checkout": "checkout", END: END},
    )
    g.add_edge("clarify", END)
    g.add_edge("checkout", END)
    g.add_edge("support", END)
    g.add_edge("merchandising", END)

    return g.compile(checkpointer=checkpointer or MemorySaver())


def make_config(deps: GraphDeps, *, thread_id: str, model: Any | None = None) -> dict[str, Any]:
    """Build the per-run config: thread_id (== conversation id) + injected deps/model."""
    configurable: dict[str, Any] = {"thread_id": thread_id, "deps": deps}
    if model is not None:
        configurable["model"] = model
    return {"configurable": configurable}


def user_turn(text: str) -> dict[str, Any]:
    """The initial state payload for a new user message."""
    return {"messages": [HumanMessage(content=text)]}


__all__ = [
    "CLARIFY_THRESHOLD",
    "MAX_PLAN_STEPS",
    "AgentState",
    "Command",
    "GraphDeps",
    "build_graph",
    "make_config",
    "user_turn",
]
