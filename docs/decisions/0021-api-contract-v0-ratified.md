# ADR-0021 — API contract v0 ratified: SSE agent chat + 5 kept defaults

- Status: Accepted
- Date: 2026-06-14
- Owner: Orion (Backend)
- Story: US-E4-00 (API contract + route/schema inventory)
- Supersedes the draft `[REVIEW]` block in `docs/api/contract-v0.md` §5.

## Context

US-E4-00 produced a contract-preview API (`api/app/`): the full route inventory mounted
as Pydantic v2 schemas with a wrapped success/error envelope, every handler a deliberate
`501` stub so the Scalar reference renders the shape for human review before any logic
exists. The draft surfaced six genuine choices as `[REVIEW]`. The human has now ratified
all six. This ADR is the durable record Week-2 build stories implement against; the
human-readable contract is `docs/api/contract-v0.md` (now marked LOCKED).

## Decisions (ratified 2026-06-14)

1. **Auth → opaque server-side session token.** Backed by `sessions(token_hash,
   expires_at)`; sent as `Authorization: Bearer <token>`; logout deletes the row →
   instant revocation. NOT a JWT — a portfolio app benefits more from honest revocation
   and using the table we already have than from stateless tokens.

2. **Success envelope → wrapped `{data, meta}`.** One envelope for every 2xx; `meta` is
   `null` for single resources, a `PageMeta` for lists. Mirrors the error envelope so
   Echo's agent tools parse one uniform shape.

3. **Pagination → opaque cursor.** `meta.next_cursor` (opaque), one style across all list
   routes; `limit` 1–100; `total` best-effort. Stable under inserts; good for the
   infinite-scroll catalog/search surfaces.

4. **Search v0 → keyword-only, semantic-ready.** Response already carries per-result
   `score` and a top-level `mode` discriminator (`SearchMode`: `keyword|semantic|hybrid`).
   pgvector retrieval drops in behind the identical shape with **no contract change**. No
   embedding dimension is baked into the API (stays embedding-agnostic). **pgvector
   retrieval is deferred to Echo in Week-2.**

5. **Agent chat → SSE STREAMING — CHANGED from the draft.** The draft defaulted to a
   single-JSON `AgentReply`; ratified instead as a `text/event-stream`. This is the
   biggest change and the one Week-2 implementers must build to.

   **Request side is unchanged JSON:** POST a user message (`MessageRequest`) or open a
   conversation with a first message (`ConversationStartRequest`) carrying
   `surface ∈ buyer|support|seller` + optional context order/product ids +
   `Idempotency-Key`. **Persisted entities are unchanged:** conversations / messages /
   agent_actions, `citations` jsonb, the `agent_outcome` enum.

   **Event protocol** (each `data:` payload is a typed model in `app/schemas/agent.py`):
   - `event: token` / `data: "<text delta>"` — `TokenEvent`; repeated 0..n, in order;
     the assistant message streamed chunk-wise.
   - `event: citations` / `data: [Citation, …]` — `CitationsEvent`; emitted when retrieval
     resolves; **may arrive after some `token` frames**.
   - `event: done` / `data: { conversation_id, message_id, action, recommendations[] }` —
     `DoneEvent`; TERMINAL. Carries the persisted `agent_actions` row (`action`, whose
     `outcome ∈ applied|refused|hitl_deferred`; null for a pure clarify/refusal), grounded
     `recommendations`, and the ids to reconcile against the transcript GET. Stream closes
     after this.
   - `event: error` / `data: { error: { code, message, details } }` — `StreamError`;
     wraps the canonical `ErrorBody` (closed `code` set) so a mid-stream failure is as
     machine-checkable as a non-2xx JSON error. Stream closes after this.

   The transcript read (`GET /agent/conversations/{id}` → `ConversationOut`) stays plain
   JSON — it reads the persisted conversation, not the live turn. The typed event payloads
   are also surfaced as named OpenAPI schemas via the reference-only route
   `GET /agent/_sse-events` → `SseEventCatalog`, so each frame's shape renders in Scalar.
   The two streaming routes advertise a single `200` content type of `text/event-stream`
   (via `response_class=StreamingResponse` + an explicit `responses` block). The contract
   stub yields an illustrative `token → citations → done` sequence; the event **order and
   payload types are the locked contract**, the placeholder strings are not.

   **Note for Iris/Echo (Week-2):** this is the streaming generative-UI surface.

6. **Test-mode payment → two-step intent → confirm, with a deterministic decline switch.**
   `POST /orders/{id}/payment-intent` then `POST /orders/{id}/payment-confirm`, mapping to
   the `payments` table + `payment_status` enum (no real PSP). The **decline trigger is the
   request body, not a side channel**: `PaymentConfirmRequest.outcome="captured"` (default)
   captures; **`outcome="failed"` forces a deterministic decline → `402 payment_declined`,
   payment row `failed`, order stays `placed` (unpaid, not cancelled).** No magic amount, no
   env flag, no randomness — so Juno's J-BUY-04 failed-checkout fixtures are stable.

## Consequences

- Week-2 agent handlers return a stream, not a JSON body. Idempotency on the streaming
  message route still applies to the *persisted* turn (replays must not double-write
  conversations/messages/agent_actions); the stream itself is re-derivable from the
  persisted record via the transcript GET. Citation assembly may complete mid-stream — the
  `citations` event is allowed to follow `token` frames.
- Iris's chat UI consumes SSE (token-by-token render) rather than awaiting one JSON reply;
  the `agent-thinking-indicator` / generative-UI testids back this.
- The five kept defaults required no code change beyond the doc lock; only the agent
  schemas + router changed for SSE.
- QA has a body-driven, deterministic payment-decline path (`outcome="failed"` → 402).
- ruff + `mypy --strict` clean; app boots; Scalar `/docs` (200) renders both agent routes
  as `text/event-stream` and lists the `*Event` payload schemas.
