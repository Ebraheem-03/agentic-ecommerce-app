# ADR-0033 — Guardrail + HITL policy: refund caps, injection defense, RAGAS v1 gate

- Status: accepted (human-ratified, Day 16)
- Date: 2026-06-24
- Owner: Atlas (decision-of-record) · Echo (implementation) · Juno (eval gate)
- Stories: US-E5-05 (hybrid RAG), US-E5-06 (support agent + HITL threshold),
  US-E5-07 (guardrails: I/O validation, injection defense, spend/refund caps),
  US-QA-D16 (RAGAS gate v1)
- Supersedes / relates: resolves the ADR-0029 `[REVIEW]` guardrail fork (no cap / no
  HITL threshold); builds on ADR-0030 (RAGAS harness + `Judge` seam), ADR-0031 (LangGraph
  orchestrator), ADR-0032 (Gemini embeddings @768), ADR-0027 (search retriever seam).

## Context

Day 16 adds the support agent, hybrid RAG, and the guardrail layer. Three of the four
stories are `[REVIEW]` — they hinge on policy the human owns, not architecture (the seams
all exist: `_check_scope`, `AgentOutcome.hitl_deferred`, `SemanticRetriever`/`HybridRetriever`,
`GeminiEmbedder`, the `Judge` Protocol). The human ratified the policy up front (Day-15
pattern) so Echo + Juno run `[AFK]` against a fixed target. This ADR is the record.

## Decisions (human-ratified)

### 1. Refund / spend guardrail — tiered autonomy (US-E5-06/07)
Replaces the ADR-0029 v0 default (owner OR support/admin, no cap, no threshold). The
support agent's `refund` action is gated by **amount tiers**, evaluated against the
captured-payment amount the refund would touch:

| Tier | Amount | Outcome | Audit `outcome` |
|---|---|---|---|
| Auto | ≤ **$50** (5000 minor) | agent executes the refund | `applied` |
| HITL | **$50–$200** (5000–20000 minor, inclusive lower-exclusive of auto) | queued for a human; refund NOT executed | `hitl_deferred` |
| Refuse | > **$200** (20000 minor) | hard-refused; refund NOT executed | `refused` |

- **Scope within the auto-tier:** the **order owner** may request a refund on their **own**
  order, and a **support/admin** may act on any order — both subject to the same tiers.
  Owner requests above the auto-cap route to support/admin via `hitl_deferred` (the owner
  cannot self-approve a >$50 refund).
- Boundaries are inclusive at $50 (auto) and inclusive at $200 (the top of HITL); strictly
  above $200 is refused. Amounts are compared in **minor units** (integer cents) to avoid
  float drift — the cap constants live as minor-unit ints.
- `hitl_deferred` is a terminal outcome for the turn: the agent tells the user the request
  is queued for a human, writes the `AgentAction` row with `outcome=hitl_deferred`, and does
  **not** mutate the `Payment`. (A human-review queue/worker is a future epic; the seam is
  the audit row + outcome value, already present from ADR-0029.)
- This lands in `_check_scope` / the executor's refund path as the concrete tier logic the
  ADR-0029 seam was reserved for. Caps are config-surfaced
  (`REFUND_AUTO_CAP_MINOR=5000`, `REFUND_HITL_CAP_MINOR=20000`) so they're tunable without a
  code change, mirroring the embedding/judge settings pattern.

### 2. Injection defense — strict boundary, log, refuse (US-E5-07)
Untrusted content — user turns AND retrieved RAG passages (product copy, policy prose,
reviews) — is treated as data, never instructions:

- **No scope/identity escalation from content.** The acting `User`/`Session`/`conversation_id`
  are closed over from request context (already true since ADR-0029/0031) and can NEVER be
  set or changed by anything the LLM emits or any retrieved text. Retrieved passages cannot
  grant a tool, raise a refund tier, or change who the actor is. This is the load-bearing
  guarantee — enforced structurally, not by prompt.
- **Detection + refusal.** Injection patterns (instruction-override "ignore previous…",
  fake system/tool framing, tool-call smuggling, data-exfiltration / "reveal your prompt"
  asks, attempts to lift the refund cap) are detected, **refused** with a safe message, and
  **logged** to `agent_actions` (`outcome=refused`, reason captured) — refusal is signal.
- **I/O validation.** Tool inputs already validate against Pydantic `extra="forbid"` models
  (422 on drift); the guardrail adds output-side checks that grounded answers cite real
  retrieved sources and refusals are honored.
- The eval suite (US-QA-D16) **must** include adversarial injection cases; the injection
  test passing is an acceptance criterion, not optional.

### 3. RAGAS gate v1 — numeric floors, armed by the live judge (US-QA-D16)
Support-policy answers must clear:

| Metric | Floor |
|---|---|
| Faithfulness | **≥ 0.90** (honors the QA-matrix sign-off) |
| Answer relevancy | **≥ 0.80** |
| Context recall | **≥ 0.70** |

Plus: **every `expects_refusal` golden item must refuse**, and the **injection test must
pass**. Failures become tracked defects (not silent), per the acceptance criteria.

- **Judge wiring (resolves the ADR-0030 `[REVIEW]`):** the numeric floors are only
  meaningful against the **live Claude judge** (`EVAL_JUDGE=claude`, `claude-opus-4-8`,
  registered-not-called in ADR-0030). The gate is therefore **armed when a live judge is
  configured** (the human's local run, key present) and falls back to the deterministic
  stub as a **CI-safe smoke** (no Anthropic key in CI → no numeric hard-fail), exactly the
  key-free pattern Day-15 established for the product brains. The product RUNTIME LLM stays
  Groq/Gemini free-tier; the eval judge is a separate, paid, local-only concern.
- Refusal-correctness and the injection test are **deterministic** and gate in CI too — they
  don't need the live judge.

**Addendum (US-E7-EJ, post-Day-16): free-tier `"llm"` judge is now the recommended armed
judge — no paid Anthropic key.** The original §3 wiring required a paid Anthropic key
(`EVAL_JUDGE=claude`) to arm the floors — the project's only paid dependency. An `LlmJudge`
(`app/eval/judge.py`, registered under `"llm"`) now scores faithfulness + answer relevancy
via the **same free-tier provider the product runtime uses** (`get_chat_model()` →
`LLM_PROVIDER` = Groq/Gemini), with structured output (a Pydantic `_ScoreOut`, clamped to
`[0,1]`; malformed output degrades to 0.0, never crashes). So **one free-tier key arms BOTH
the runtime and the eval gate** — `EVAL_JUDGE=llm` is the recommended path. The arming check
(`gate.is_armed`) was already general (any non-`deterministic:` identity arms), so `LlmJudge`
(identity `llm:<provider>:<model>`) arms exactly like Claude with no gate change; the
`DeterministicJudge` smoke (CI default, key-free) is unchanged. `ClaudeJudge` stays
registered as an **optional** paid judge. No new `[REVIEW]` — this is a free-tier swap of the
already-ratified `Judge` seam.

## Consequences

- The ADR-0029 guardrail fork is closed: `refund` now has a real cap + HITL threshold, and
  owner-vs-support scope is settled (owner may self-serve only within the auto-cap).
- The support agent has a bounded, auditable autonomy envelope; every tier decision leaves an
  `AgentAction` row, so QA asserts on outcomes, not prose.
- Injection defense is structural-first (identity/scope can't be talked out of) with a
  detect-log-refuse layer on top; the adversarial eval keeps it honest.
- The RAGAS gate is real by code and green by code: hard numbers locally with the Claude
  judge, refusal+injection determinism everywhere, no key required for CI.
- Deferred (seams in place, not blocking): a real HITL review queue/worker to drain
  `hitl_deferred` rows; partial refunds / restock-on-refund (still the returns epic, ADR-0028).
