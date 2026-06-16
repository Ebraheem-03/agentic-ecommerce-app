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

import time
from typing import Any, Literal, Protocol

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agent.trace import record_model_call
from app.core.config import settings

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


SupportIntent = Literal["policy", "order_status", "refund"]


class SupportPlan(BaseModel):
    """The support agent's decision for a turn (US-E5-06).

    The support node executes deterministically off this plan (RAG retrieval, orderStatus,
    refund-with-tiering all live in the node + executor, NOT the LLM). The brain only
    decides WHICH of the three support intents the turn is and extracts the needed args:

      * ``policy``       -> ground the answer in retrieved policy docs (the RAG path);
      * ``order_status`` -> look up ``order_id`` via the orderStatus tool;
      * ``refund``       -> request a refund on ``order_id`` (the executor applies the
        HITL tier; the brain NEVER decides the tier — that's structural guardrail logic).

    ``query`` is the policy-retrieval query for the ``policy`` intent (defaults to the
    user's message). The brain cannot set identity/scope/amount — those are closed over.
    """

    intent: SupportIntent = Field(description="Which support capability this turn needs.")
    query: str = Field(
        default="", description="Policy-search query (for the policy intent)."
    )
    order_id: str = Field(
        default="", description="Order id (for order_status / refund intents)."
    )
    reason: str = Field(default="", description="Optional refund reason / short rationale.")


class MerchListing(BaseModel):
    """A generated DRAFT listing's copy (US-E5-08, ADR-0034 §3).

    The merchandising brain produces ONLY the listing COPY — title, description,
    category, attributes — grounded in the seller's brief + retrieved comparable
    products. It does NOT set the price (the price SUGGESTION is computed structurally
    in ``app.agent.merch`` from real comparable catalog rows, surfaced with its basis —
    never invented by the model), and it never publishes (the draft persists with a
    ``draft`` status; seller approval is a future story).
    """

    title: str = Field(description="A concise, appealing product title.")
    description: str = Field(description="A grounded 1-3 sentence product description.")
    category: str = Field(default="", description="The product category (e.g. 'Home').")
    attributes: dict[str, str] = Field(
        default_factory=dict, description="Key product attributes (material, size, ...)."
    )


# --------------------------------------------------------------------------- #
# Protocols — the injection seam.                                              #
# --------------------------------------------------------------------------- #
class IntentClassifier(Protocol):
    def classify(self, history: list[BaseMessage]) -> IntentResult: ...


class ShoppingPlanner(Protocol):
    def plan(
        self, history: list[BaseMessage], tool_results: list[str]
    ) -> PlannerStep: ...


class SupportBrain(Protocol):
    def plan(self, history: list[BaseMessage]) -> SupportPlan: ...


class MerchBrain(Protocol):
    def draft(self, brief: str, comparables: list[str]) -> MerchListing: ...


# --------------------------------------------------------------------------- #
# Default LLM-backed implementations (used in prod; not exercised by CI).      #
# --------------------------------------------------------------------------- #
def _provider_model() -> tuple[str, str]:
    """The configured runtime (provider, model) for the trace's model-call record."""
    provider = settings.llm_provider
    model = settings.gemini_model if provider == "gemini" else settings.groq_model
    return provider, model


def _invoke_traced(model: Any, ctx: list[BaseMessage], *, node: str) -> Any:
    """Invoke the chat model and record the call on the ambient trace (best-effort).

    Captures the rendered prompt, latency, and (when the response carries it) token usage
    so the trace's model-call record is populated for a live provider; under a scripted
    brain this path is never reached, so tokens record as null gracefully (US-E7-04).
    """
    prompt = "\n".join(str(getattr(m, "content", m)) for m in ctx)
    provider, model_name = _provider_model()
    t0 = time.perf_counter()
    result = model.invoke(ctx)
    latency_ms = (time.perf_counter() - t0) * 1000
    record_model_call(
        node=node,
        provider=provider,
        model=model_name,
        prompt=prompt,
        response=result,
        latency_ms=latency_ms,
    )
    return result


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
        result = _invoke_traced(self._model, [_CLASSIFY_SYSTEM, *history], node="classify")
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
        result = _invoke_traced(self._model, ctx, node="shopping")
        assert isinstance(result, PlannerStep)
        return result


_SUPPORT_SYSTEM = SystemMessage(
    content=(
        "You are Ember's support assistant. Decide which ONE capability the user's latest "
        "message needs: 'policy' (returns, shipping, payments, care, how-it-works "
        "questions answered from store/platform policy), 'order_status' (where is my "
        "order / its status), or 'refund' (the user wants money back on an order). For "
        "'policy', set `query` to a concise search query for the policy docs. For "
        "'order_status'/'refund', set `order_id` if the user gave one. NEVER decide "
        "whether a refund is allowed or how large — only classify the intent; the system "
        "enforces refund limits and human review. Ground every answer in retrieved policy "
        "text; never invent policy."
    )
)


class LLMSupportBrain:
    """Classify the support turn into a ``SupportPlan`` via structured output (default brain).

    Like the other brains, the REASONING is the LLM's but the ACTION is the node's: the
    node runs RAG / orderStatus / refund off this plan. The brain cannot set identity,
    scope, or a refund amount/tier — those are closed over from request context + enforced
    by the executor's guardrails, never by model output.
    """

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model.with_structured_output(SupportPlan)

    def plan(self, history: list[BaseMessage]) -> SupportPlan:
        result = _invoke_traced(self._model, [_SUPPORT_SYSTEM, *history], node="support")
        assert isinstance(result, SupportPlan)
        return result


_MERCH_SYSTEM = SystemMessage(
    content=(
        "You are a merchandising assistant helping a SELLER draft a product listing. From "
        "the seller's brief and a list of REAL comparable products from the catalog, write "
        "a concise title, a grounded 1-3 sentence description, a category, and key "
        "attributes. Ground the copy in the seller's brief and the comparables — do NOT "
        "invent specs, brands, or competitor claims. You do NOT set the price (the system "
        "computes a suggestion from the real comparables) and you do NOT publish — this is "
        "a DRAFT a human approves."
    )
)


class LLMMerchBrain:
    """Generate a draft listing's COPY via structured output (the default merch brain).

    Like the other brains, the REASONING is the LLM's but the ACTION is the node's: the
    merch node retrieves comparables, computes the price suggestion structurally, and
    persists the DRAFT (never publishes). The brain cannot set price, identity, or store —
    those are closed over / computed, never from model output.
    """

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model.with_structured_output(MerchListing)

    def draft(self, brief: str, comparables: list[str]) -> MerchListing:
        ctx: list[BaseMessage] = [_MERCH_SYSTEM, HumanMessage(content=brief)]
        if comparables:
            ctx.append(
                SystemMessage(
                    content="Comparable products (real catalog rows):\n"
                    + "\n".join(comparables)
                )
            )
        result = _invoke_traced(self._model, ctx, node="merchandising")
        assert isinstance(result, MerchListing)
        return result


__all__ = [
    "IntentClassifier",
    "IntentResult",
    "LLMIntentClassifier",
    "LLMMerchBrain",
    "LLMShoppingPlanner",
    "LLMSupportBrain",
    "MerchBrain",
    "MerchListing",
    "PlannerStep",
    "Route",
    "ShoppingPlanner",
    "SupportBrain",
    "SupportIntent",
    "SupportPlan",
    "ToolCall",
]
