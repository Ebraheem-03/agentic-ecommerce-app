# ADR-0031 — Product agent runtime: LangChain + LangGraph orchestrator, provider-swap, interrupt approval gate

- Status: accepted
- Date: 2026-06-23
- Owner: Echo (AI/Agents)
- Stories: US-E5-03 (orchestrator/router + session state), US-E5-04 (shopping agent, agentic-checkout plan-execute)
- Supersedes / relates: ADR-0029 (agent tool layer + executor), ADR-0021 (agent SSE contract),
  ADR-0030 (RAGAS harness — separate eval-judge LLM), ADR-0026/0027 (embedding/search seams),
  ADR-0028 (order lifecycle/payment)

## Context

The product's own agents (shopping today; support Day 16; merchandising Day 17) need a
runtime that classifies intent, routes to an agent, runs a plan-execute shopping turn, and
— critically — STOPS for explicit human approval before placing any order. The
architecture (LangChain + LangGraph) was ratified by the human on 2026-06-23; this ADR
records how it is built on top of the Week-2 tool layer (ADR-0029) and the locked SSE
contract (ADR-0021), without reimplementing any business logic.

New modules under `api/app/agent/`: `llm.py` (provider factory), `brains.py` (injectable
LLM reasoning behind the nodes), `graph.py` (the `StateGraph`), `langchain_tools.py`
(LangChain tool adapter over the executor), `persistence.py` (durable conversation rows),
`runner.py` (drive the graph + emit SSE). The SSE routes in `app/api/routers/agent.py`
(previously 501-stub illustrative streams) are now wired to a real turn.

## Decisions

### 1. Provider-swappable chat model (Groq AND Gemini), one config line
`app/agent/llm.py::get_chat_model()` resolves `settings.llm_provider` →
`langchain_groq.ChatGroq` | `langchain_google_genai.ChatGoogleGenerativeAI` via a closed
`_PROVIDERS` registry (mirrors `get_embedder`/`get_retriever`/`_JUDGES`). Unknown provider
or a missing key → **fail loud** (`RuntimeError`). New `config.py` settings: `llm_provider`
(default `"groq"`), `groq_api_key`, `gemini_api_key`, `groq_model`
(`llama-3.3-70b-versatile`, current free-tier default), `gemini_model`
(`gemini-2.0-flash`). `model_config` now loads a **gitignored `.env`** (`env_file=".env"`,
`extra="ignore"`) so the human's real keys live outside the repo while process-env still
overrides; bare `DATABASE_URL`/`EMBED_DIM` still resolve. **Groq is the primary; Gemini is
configured now but the fallback CHAIN is Day-17 (US-E5-09)** — not built here.

### 2. LangGraph `StateGraph` orchestrator + routing policy (human-ratified)
A single compiled graph:

```
classify ──low-confidence──▶ clarify ─▶ END
   │ (route)
   ├─ shopping ─▶ (plan-execute loop) ─▶ [interrupt: approve] ─▶ checkout ─▶ END
   ├─ support  ─▶ deferred ("not available yet") ─▶ END   (Day 16)
   └─ merch    ─▶ deferred ("not available yet") ─▶ END   (Day 17)
```

- **`classify`** is an LLM intent-classification node using **structured output**
  (`with_structured_output(IntentResult)`) → `route ∈ {shopping, support, merchandising}` +
  a calibrated `confidence`.
- **Ambiguity fallback (human-ratified):** when `confidence < CLARIFY_THRESHOLD` (0.55) the
  router does NOT guess and does NOT dead-end — it routes to the **shopping agent with ONE
  clarifying turn**.
- **support / merchandising are REGISTERED-but-deferred nodes:** they return a graceful
  "not available yet" assistant message — never a 501/crash.

### 3. Shopping agent: plan-execute with a HARD approval stop
`shopping` runs a bounded (`MAX_PLAN_STEPS=6`) plan-execute loop: the planner either calls
discovery/cart tools (search / productDetails / inventory / applyCoupon / addToCart),
replies with a grounded message, or **proposes checkout**. A checkout proposal routes to
`approve_checkout`, which calls LangGraph **`interrupt()`** and surfaces the plan. The graph
PAUSES before any order is placed. Only an explicit resume with
`Command(resume={"approved": True, ...})` runs the `checkout` node, which places the order
via the **real `draftOrder` tool** (the Week-2 executor — reserve/intent, audited). A
rejection ends the turn with no side effect. This is the contract's "agentic checkout" with
a mandatory human-in-the-loop gate.

### 4. Reuse the Week-2 tool layer — thin adapter, no reimplementation
`langchain_tools.py` wraps each tool as a `StructuredTool` whose `func` is a thin closure
over `execute_tool` (ADR-0029): the existing Pydantic input model is the `args_schema`, and
validation/scope/idempotency/retry/audit/error-envelope all stay in the executor. The graph
also drives tools directly through `execute_tool` (same path). **The acting `User` + the
shared `Session` + `conversation_id` are closed over from the request context (resolved via
`app/api/deps.py::require_user`), NEVER taken from the LLM** — one identity path for humans
and agents; the model can't escalate scope by arguments. `draftOrder`/`refund` are NOT
exposed to the autonomous loop (order placement goes through the approval gate; refund is
the Day-16 support agent).

### 5. Session state: in-graph checkpointer + durable ORM record
The graph is compiled with a **checkpointer keyed on `thread_id` == `conversation.id`** so
an interrupted turn resumes. The **durable record** of turns lives in our existing
`conversations` / `messages` tables (`persistence.py`) + `agent_actions` (executor audit) —
the checkpointer is in-graph thread state only. The transcript GET reads the durable record,
not graph internals. `MemorySaver` is the default checkpointer (fine for a single process /
tests); a durable checkpointer is a later wiring concern.

### 6. Injectable brains — the CI key-free contract
`langchain_core`'s fake chat models do not implement `with_structured_output` / native
tool-calling, so a graph driving a fake model directly is untestable without a live key.
The reasoning is therefore injected behind two Protocols (`brains.py`): `IntentClassifier`
and `ShoppingPlanner`. The defaults (`LLMIntentClassifier` / `LLMShoppingPlanner`) wrap the
chat model; **tests inject deterministic stubs** so CI runs the real graph structure,
routing policy, interrupt gate, and real-service side effects **with no provider key**. The
SSE route exposes a `_DEPS_OVERRIDES` seam for the same reason.

### 7. SSE wiring (contract-v0)
`runner.py::stream_turn` drives a turn and yields the locked SSE frames
(`token → [approval] → citations → done`); `app/api/routers/agent.py` wires the two POST
routes to it (auth-scoped via `require_user`) and the transcript GET to the durable record.
Because a `StreamingResponse` body runs AFTER request dependencies close, the streaming
generator owns its own session txn (`_turn_session` → commit/rollback/close). Token
streaming is chunked from the computed final text today; **true token-by-token LLM streaming
is a later refinement** — the contract SHAPE is honored now.

## Consequences

- **One config line flips the runtime LLM provider** (Groq↔Gemini); unknown/missing-key
  fails loud. Real keys are gitignored; CI is key-free.
- **No order is ever placed without explicit human approval** — enforced by a graph-level
  `interrupt()`, proven by tests (order count unchanged at the interrupt; placed only on
  resume-approved).
- **Zero duplication of business logic** — the agent acts entirely through the Week-2
  executor (scope/idempotency/audit/error-envelope reused).
- **Deferred (carried to the human, non-blocking):** (1) durable LangGraph checkpointer for
  multi-request resume (today the SSE single-request path surfaces the approval frame and
  the client resumes via a re-invocation that reuses the thread); (2) true token-by-token
  streaming; (3) the Groq/Gemini **fallback chain + semantic cache** (US-E5-09, Day 17);
  (4) a **live-key smoke** of the real provider path (CI/tests never call it).

## Open `[REVIEW]` for the human
- **Routing policy** — confirm: LLM classify with structured output; ambiguous
  (confidence < 0.55) → shopping agent + one clarifying turn (no silent guess, no dead-end);
  support/merch deferred-but-graceful.
- **Checkout approval (HITL)** — confirm the HARD `interrupt()` stop before ANY order /
  payment, resume-to-execute only on explicit approval.
- **Provider keys** — supply real `GROQ_API_KEY` (primary) in the gitignored `.env` for the
  live smoke; Gemini key optional until Day-17 fallback.
- (Refund spend-cap + HITL threshold from ADR-0029 remains open — it lands with the Day-16
  support agent + the guardrail epic.)
