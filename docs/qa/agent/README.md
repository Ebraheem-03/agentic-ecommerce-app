# Agent conversation E2E pack (US-QA-D15)

A multi-turn **agent conversation** driven through Echo's real LangGraph runtime
(`api/app/agent/runner.py` → `graph.py`) against a freshly-seeded throwaway DB. It proves
one buyer's shopping session works end-to-end and emits a **transcript + tool-call-accuracy**
artifact.

Test module: `api/tests/agent/test_agent_convo_e2e.py`.

## The journey

One conversation (`thread_id == conversation.id`), four user turns:

```
search ──▶ product comparison ──▶ add-to-cart ──▶ propose checkout
   │            │                     │                │
 search    productDetails×2        addToCart      interrupt() HARD STOP
 (grounded) (session continuity)  (real cart line)  no order yet
                                                       │
                                            resume(approve) ─▶ draftOrder ─▶ order placed
```

A second isolated conversation covers the **reject fork**: `resume(reject)` → no order.

Every turn runs on a **scripted brain** (the `app.agent.brains` injection seam) so routing
and tool selection are deterministic with **no provider key** (CI-safe). Products/variants
are resolved from the seed via the `handles` fixture (anti-drift); nothing is hand-seeded.

## What it asserts (and what it does NOT)

This is the **journey-level** layer. It does **not** re-assert Echo's atoms — per-node
behavior, each route, the classifier/factory seam, interrupt mechanics, and the SSE
contract shape live in `api/tests/agent/test_orchestrator.py` and `test_agent_sse_e2e.py`.

| Surface | Per-feature suite (atoms) |
| --- | --- |
| orchestrator nodes / routing / interrupt mechanics | `tests/agent/test_orchestrator.py` |
| SSE contract (token → citations → done) | `tests/agent/test_agent_sse_e2e.py` |
| LLM factory / provider swap | `tests/agent/test_llm_factory.py` |
| per-tool E2E matrix | `tests/agent/test_tool_e2e.py` (US-QA-D12) |

This pack adds the cross-turn invariants only a stitched conversation has:

- **session continuity** — turns 2–4 reuse turn 1's `conversation_id`/`thread_id`; the
  durable transcript accumulates 4 user + 4 assistant turns in order;
- **real cart effect** — `addToCart` lands a `CartItem` for the resolved variant at the
  right qty in the buyer's open cart;
- **hard approval stop** — across the whole conversation **no `Order` exists** until an
  explicit approval; the approve/reject fork diverges exactly at the `interrupt()`;
- **one catalog** — searched / compared / carted / ordered rows all resolve to the same
  seeded handles;
- **tool-call accuracy** — expected tools (the script) vs **actual** tools called, where
  "actual" is read from the executor's own `AgentAction` audit rows (the authoritative
  record of what really ran), not echoed from the stub.

## Tool-call accuracy

`tool_call_accuracy = |expected ∩ actual| / |expected|` as an order-insensitive multiset
over the whole conversation. The journey is scripted to a correct plan, so the test gates
on **accuracy == 1.0** (every expected tool really executed against the real services).
The per-turn expected-vs-actual breakdown is in the artifact.

## Running it (one command, clean seed)

DB up (compose `pgvector/pgvector:pg16`). Host 5432 is often occupied → use an alt host
port. From `api/`, with the venv:

```bash
DB_PORT=55444 docker compose up -d db   # from repo root, once

cd api
DATABASE_URL=postgresql+psycopg://postgres:CHANGE_ME@localhost:55444/agentic_ecommerce \
  .venv/bin/python -m pytest tests/agent/test_agent_convo_e2e.py -s
```

`-s` surfaces the printed accuracy summary + artifact path. Each test gets a pristine
migrated + seeded throwaway DB (per-test CREATE/DROP via `migration_db` → `seeded_db`), so
the journey always runs from a clean seed.

## The artifact

On run the test writes, under this directory:

- `agent-convo-<date>.json` — the machine-readable transcript + per-turn tool calls +
  accuracy roll-up (gitignored, regenerated each run);
- `agent-convo-<date>.md` — a skimmable Markdown transcript (gitignored);
- `agent-convo-latest.{json,md}` — stable pointers to the most recent run (gitignored).

Only this `README.md` is committed; the `agent-convo-*` outputs are gitignored exactly like
the Day-10 `retrieval-smoke-*.json` and Day-13 `regression-*.md` artifacts, so the tree /
CI never churn on wall-clock stamps. The artifact is **informational** (what Atlas / the
human skim) — the gate is the green test.
