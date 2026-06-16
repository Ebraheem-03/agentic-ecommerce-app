# Agent observability — local trace store (US-E7-04, ADR-0042 §D1)

This directory holds the product agent layer's **local structured trace store**: one
JSONL trace per agent run, written by the LangGraph runtime. It is the answer to
"what did the agent actually do this turn, what did it send the model, and what did it
cost?" — without any external SaaS, API key, or data egress.

## What a trace records

One `RunTrace` (one line in `results/<run_id>.jsonl`) carries, per turn:

- `trace_id`, `run_id`, `conversation_id` (the thread), `route`
  (shopping / support / merchandising / clarify), `started_at`, total `latency_ms`;
- `node_spans` — each LangGraph node that ran, with its own `latency_ms`;
- `tool_calls` — each executor tool call (`name`, a compact `args_summary`, `outcome`
  ∈ applied / refused / hitl_deferred / error / blocked), read at the authoritative
  `execute_tool` audit point;
- `model_calls` — each chat-model invocation (`node`, `provider`, `model`, the `prompt`
  sent, `tokens_in` / `tokens_out`, `cost_usd`, `latency_ms`). Token usage is read from
  the LangChain response `usage_metadata` / `response_metadata` where available; when it
  is absent (e.g. the key-free scripted brains used in CI) the token/cost fields are
  recorded as `null` / `0.0` gracefully — a turn never fails because tracing did;
- `tokens_in` / `tokens_out` / `cost_usd` — turn-level roll-ups across the model calls;
- `disposition` — the terminal outcome: `reply` / `clarify` / `refusal` /
  `checkout_proposed` / `fallback`.

## Cost model

Cost is computed from a small per-provider/model price table in `app/agent/trace.py`
(`_PRICE_TABLE`, USD per 1M tokens, split input/output). Groq and Gemini free-tier rows
are `0.0` today, but the field and the table are modelled so a **paid** model (e.g. the
example `anthropic:claude-opus-4-8` row) computes a real cost from real usage. Unknown
models fall back to the provider wildcard row, then `0.0`.

## Configuration

- `OBS_ENABLED` (default `true`) — gates tracing entirely. `false` makes the runtime a
  pure no-op (no traces written, zero overhead beyond a contextvar read).
- `OBS_BACKEND` (default `local`) — the dormant-seam selector. `local` is the only active
  path (writes here). `langsmith` is a **registered but dormant** seam: there is no
  langsmith hard-dependency, so selecting it logs once and degrades to the local writer
  (the trace is never lost). A future hosted run is a one-flag change without taking on a
  dependency today.

## Artifacts

`results/<run_id>.jsonl` files are **gitignored** (regenerated every run), the same
convention as `docs/qa/eval/results/` and `docs/qa/agent/`. Only this README is committed.

Every failing E2E / eval case can be linked back to its trace by `run_id` (US-QA-D23).
