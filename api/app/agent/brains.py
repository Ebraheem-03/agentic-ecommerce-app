"""The LLM-backed 'brains' behind the graph nodes (US-E5-03/04, ADR-0031).

The LangGraph nodes (``graph.py``) are deliberately thin: they own control flow, state,
the ``interrupt()`` approval gate, and persistence. The *reasoning* — classify the user's
intent, decide the next shopping step — lives behind two small Protocols here so it is
fully INJECTABLE:

  * ``IntentClassifier.classify(history) -> IntentResult`` — routes a turn to
    shopping | support | merchandising, with a confidence the router uses for the
    ambiguity fallback. The default ``LLMIntentClassifier`` uses the chat model's
    ``with_structured_output`` (structured output, as required); tests inject a stub.
  * ``ShoppingPlanner.plan(history, tool_results) -> PlannerStep`` — the plan-execute
    step: either CALL discovery/cart tools, PROPOSE a checkout (-> the approval
    interrupt), or REPLY with a final grounded message. The default ``LLMShoppingPlanner``
    binds the shopping tools to the chat model; tests inject a stub.

Why a function-level seam (not the raw chat model)? ``langchain_core``'s fake chat models
don't implement ``with_structured_output`` / native tool-calling, so a graph that drove a
fake model directly couldn't be tested without a live key. Injecting the brain keeps the
graph structure real AND keeps CI key-free — the human's hard requirement.
"""

from __future__ import annotations

from typing import Literal, Protocol

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage
from pydantic import BaseModel, Field

# The three product agents the orchestrator routes to. shopping is built today;
# support (Day 16) + merchandising (Day 17) are registered-but-deferred nodes.
Route = Literal["shopping", "support", "merchandising"]


class IntentResult(BaseModel):
    """The classifier's verdict: which agent + how confident."""

    route: Route = Field(description="Which agent should handle this turn.")
    confidence: float = Field(
        ge=0.0, le=1.0, description="0..1 confidence in the route. Low -> clarify."
    )
    reason: str = Field(default="", description="One short phrase: why this route.")


class ToolCall(BaseModel):
    """A single tool the planner wants the graph to execute this step."""

    name: str
    args: dict[str, object] = Field(default_factory=dict)


class PlannerStep(BaseModel):
    """One plan-execute decision from the shopping planner.

    Exactly one mode is active:
      * ``tool_calls`` non-empty -> run them, feed results back, plan again;
      * ``propose_checkout`` True -> the user wants to buy: the graph raises the
        approval ``interrupt()`` with ``checkout_summary`` before any order is placed;
      * otherwise -> ``reply`` is the final grounded assistant message for the turn.
    """

    tool_calls: list[ToolCall] = Field(default_factory=list)
    propose_checkout: bool = False
    checkout_summary: str = Field(
        default="", description="Human-readable plan to approve (when proposing checkout)."
    )
    reply: str = Field(default="", description="Final assistant message (when replying).")


# --------------------------------------------------------------------------- #
# Protocols — the injection seam.                                              #
# --------------------------------------------------------------------------- #
class IntentClassifier(Protocol):
    def classify(self, history: list[BaseMessage]) -> IntentResult: ...


class ShoppingPlanner(Protocol):
    def plan(
        self, history: list[BaseMessage], tool_results: list[str]
    ) -> PlannerStep: ...


# --------------------------------------------------------------------------- #
# Default LLM-backed implementations (used in prod; not exercised by CI).      #
# --------------------------------------------------------------------------- #
_CLASSIFY_SYSTEM = SystemMessage(
    content=(
        "You are the router for an e-commerce assistant. Classify the user's latest "
        "message into exactly one route: 'shopping' (browse/search products, cart, "
        "checkout), 'support' (order status, returns, refunds, account help), or "
        "'merchandising' (a SELLER creating/pricing a listing). Give a calibrated "
        "confidence in [0,1]; use a LOW confidence when the message is ambiguous or "
        "could fit multiple routes."
    )
)


class LLMIntentClassifier:
    """Classify intent via the chat model's structured output (the default node brain)."""

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model.with_structured_output(IntentResult)

    def classify(self, history: list[BaseMessage]) -> IntentResult:
        result = self._model.invoke([_CLASSIFY_SYSTEM, *history])
        assert isinstance(result, IntentResult)
        return result


_PLAN_SYSTEM = SystemMessage(
    content=(
        "You are Ember, a grounded shopping assistant. Help the user discover products "
        "(search, productDetails, inventory), apply coupons, and add items to their cart. "
        "Only recommend products you have retrieved — never invent details. When the user "
        "is ready to buy, PROPOSE checkout with a clear summary; do NOT place the order "
        "yourself (a human must approve it first)."
    )
)


class LLMShoppingPlanner:
    """Plan the next shopping step by binding the shopping tools to the chat model.

    The default brain emits a ``PlannerStep`` via structured output. A real run threads
    the tool results back into ``history`` between steps (the graph drives the loop).
    """

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model.with_structured_output(PlannerStep)

    def plan(
        self, history: list[BaseMessage], tool_results: list[str]
    ) -> PlannerStep:
        ctx: list[BaseMessage] = [_PLAN_SYSTEM, *history]
        if tool_results:
            ctx.append(
                SystemMessage(content="Tool results so far:\n" + "\n".join(tool_results))
            )
        result = self._model.invoke(ctx)
        assert isinstance(result, PlannerStep)
        return result


__all__ = [
    "IntentClassifier",
    "IntentResult",
    "LLMIntentClassifier",
    "LLMShoppingPlanner",
    "PlannerStep",
    "Route",
    "ShoppingPlanner",
    "ToolCall",
]
