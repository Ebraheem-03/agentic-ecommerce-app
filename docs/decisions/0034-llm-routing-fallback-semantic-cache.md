# ADR-0034 — LLM routing + fallback + semantic cache (non-personalized)

- Status: accepted (human-ratified, Day 17)
- Date: 2026-06-25
- Owner: Atlas (decision-of-record) · Echo (implementation) · Juno (eval gate)
- Stories: US-E5-08 (merchandising agent), US-E5-09 (LLM routing + fallback + semantic
  cache), US-QA-D17 (agent evals: fallback, cache hit, merch draft quality, tool-call F1)
- Supersedes / relates: builds on ADR-0031 (LangGraph orchestrator + `get_chat_model()`
  one-line provider swap), ADR-0033 (guardrail/HITL + injection defense — the cache MUST sit
  behind the injection scan), ADR-0032 (Gemini embeddings @768 — the cache key embedding),
  ADR-0027/0026 (retriever + embedding-provider seams), ADR-0029 (executor scope/ownership
  — the per-user `404-no-leak` invariant the cache must not erode).

## Context

Day 17 makes the LLM wiring real: a provider-failover path on top of the existing
`get_chat_model()` swap, and a semantic cache so repeated/similar prompts skip the LLM call.
US-E5-09 is `[REVIEW]` because the cache touches PII/tenant-isolation, not just architecture.
Two policy forks were ratified by the human up front (Day-15/16 pattern) so Echo builds
`[AFK]` against a fixed target; Echo + Orion were both consulted and **independently,
unanimously recommended the non-personalized cache (Option A)** with the guards below. This
ADR is the record. The product runtime LLM stays **Groq/Gemini free-tier** (keys live since
Day 15: Groq `llama-3.3-70b-versatile` primary ✓, Gemini `gemini-flash-latest` ✓).

## Decisions (human-ratified)

### 1. Provider routing + fallback — auto-cascade on transient only (US-E5-09)
- **Groq is primary** (unchanged default); **Gemini is the fallback**. The existing
  `LLM_PROVIDER` one-line swap (ADR-0031) still selects the primary; this adds **runtime
  failover** on top of it.
- **Fallback triggers on transient failures ONLY**: provider rate-limit (HTTP 429), timeout,
  and 5xx provider errors — after a **bounded retry** of the primary (mirror the executor's
  `TransientToolError` retry posture, ADR-0029). On exhaustion of the primary's retries, fall
  through to the secondary provider once.
- **Domain errors never trigger fallback.** Anything that is an `APIError` /
  validation / guardrail refusal is a deterministic outcome, not a provider hiccup — it
  surfaces straight through the canonical error envelope (`{"error":{code,message,details}}`),
  never silently retried on the other provider (would mask real bugs + double latency).
- If **both** providers are exhausted, surface a canonical envelope (e.g. `rate_limited`
  429 / a provider-unavailable code) — never a raw exception, never a fabricated answer.
- The failover wraps the chat-model call centrally (around `get_chat_model()` /
  `brains.py` invocation) so all three brains inherit it; no per-node duplication.

### 2. Semantic cache — NON-PERSONALIZED ONLY (Option A) (US-E5-09)
The cache keys LLM responses by prompt-embedding cosine similarity so paraphrased/repeated
prompts skip the LLM round-trip. It is allowed to cache **only tenant-shared, non-personalized
calls** — and nothing else. The value is **cross-user sharing**: a cache entry created by any
user accelerates every subsequent user asking a semantically-similar question, which is
exactly the high-volume, high-overlap surface (intent classification fires every turn; FAQ /
policy questions repeat across thousands of users). Personalized turns are *not* a missed win
— their underlying data is live/per-user and must not be cached by anyone.

**Cacheable (the allow-list):**
- **Intent classification** (`IntentResult` / classify node) — input is the raw utterance +
  fixed system prompt, no identity, no PII. This is the primary, every-turn win.
- **Grounded policy-RAG answers** keyed on shared policy docs (when/if the answer becomes an
  LLM call — today the policy answer is verbatim retrieval, so the classifier is the concrete
  win now; the policy-answer cache compounds as that path becomes generative).

**NEVER cache (binding):**
- Anything from the **shopping node** or carrying `tool_results` (cart / order / payment).
- Any **tool-result-derived** output: `order_status`, `draft_order`, `add_to_cart`,
  `apply_coupon`, `refund`, `inventory`, product detail with live stock signals.
- Anything containing **PII / order / cart / payment / address** data.
- Any **refusal / HITL / `refused` outcome**, and **any turn where `scan_for_injection`
  fired**.
- Never memoize an **`APIError`** — cache successes only. A cache-lookup failure must degrade
  to a live LLM call, never surface as `internal_error` (the cache is an optimization, not a
  caller-visible code path).

**Ordering (load-bearing, from ADR-0033):** per turn the order is
**`scan_for_injection` → cache lookup → brain/LLM → cache store**. The cache must NEVER sit
ahead of the injection scan — otherwise a paraphrased malicious prompt that collides with a
cached benign one skips injection defense and the `agent_actions` audit row.

**Scoping & key composition:**
- Policy-cache entries are **store-scoped** — `store_id` is part of the key (platform vs
  store policies fuse in `retrieve_policies`; a store-A shopper must not be served store-B
  policy). The classifier cache is global-safe (no identity in the verdict).
- Key folds in **`provider + model + node_type + embed_provider + embed_dim`** (a
  provider/dim swap must not serve vectors from a different space; `node_type` namespacing
  means a shopping prompt can never resolve a support entry).
- **Similarity threshold: cosine ≥ 0.95** (high — a paraphrase, not a topic match; semantic
  false-positives silently serve a wrong answer). Tunable via config like the other caps.
- **Stub-embedder fallback:** under `EMBED_PROVIDER=stub` (CI default) the embedding
  similarity is noise → **fall back to exact normalized-prompt match** so the cache can't
  mis-hit. Real semantic hits require `EMBED_PROVIDER=gemini`.

**Storage & invalidation:**
- **Storage = Postgres / pgvector** (Redis is not available; in-process is per-worker and
  cold on every Render restart/scale-out). Reuse the existing embeddings/pgvector seam (a
  cache table with a `vector(EMBED_DIM)` query-embedding + HNSW cosine, normalized prompt,
  response JSON, grounded `source_ids[]`, model/provider, `created_at`). *(Pragmatic
  allowance: a per-process cache is acceptable as an internal first cut iff it is keyed
  identically and the pgvector-backed store is the committed target — but the ADR's target is
  the durable pgvector store so cache hits survive restarts and span workers.)*
- **Content-version invalidation is primary; TTL is the backstop.** Key/invalidate on the
  grounded `source_id`s + the policy row version (`updated_at`), so a policy edit busts stale
  entries — the existing `refresh_*` write path is where a version bump hangs. TTL backstop:
  classifier 24h, policy-RAG 1h.

### 3. Merchandising agent — DRAFT only, never auto-publish (US-E5-08)
`[AFK]`, but the autonomy posture is fixed here so it mirrors the checkout/refund HITL stance:
- The merchandising agent generates a **draft listing** (title/description/attributes) +
  **comparables-based price suggestion** and persists it as a **draft** — it **never
  publishes to the live catalog**. A seller approves before anything goes live (same
  human-in-the-loop spirit as the `interrupt()` checkout gate and the refund tiers).
- **Comparables pricing** is grounded in real seeded catalog rows (same-category / similar
  products via the retrieval seam), surfaced as a **suggestion with its basis**, not an
  opaque number. No invented competitor data.
- Runs **async** (generation off the request's critical path) per the story; the draft is
  retrievable once ready. Identity/scope flows from `require_user` (seller role) — never from
  model output, same as every other tool.
- Guardrail-first like the other nodes: scan the seller's input + any retrieved passages
  before generation; injection/PII never settable by content.

## Consequences

- The `get_chat_model()` swap becomes a real availability story: Groq outages/limits fail over
  to Gemini automatically on transient errors, while deterministic failures still surface
  honestly through the error envelope.
- The semantic cache cuts per-user latency on the every-turn classification step (and FAQ /
  policy turns) via cross-user sharing, with **zero** cross-user PII/leakage surface — the
  executor's `404-no-leak` per-user scope (ADR-0029) is untouched because personalized turns
  are never cached.
- US-QA-D17 (Juno/Echo) must produce an eval report with **pass/fail, token cost, latency,
  and failing traces**, covering: provider fallback (forced-transient → Gemini serves),
  semantic-cache hit (paraphrase → cache, with the latency/cost delta shown), merchandising
  draft quality, and **tool-call F1** (precision/recall on tool selection, extending the
  Day-15 tool-call-accuracy artifact). Cache + fallback assertions are deterministic →
  gate in CI key-free (forced via injected transient errors + the stub-embedder exact-match
  tier); the LLM-judged quality numbers arm under the free-tier `"llm"` judge (ADR-0033
  addendum), smoke otherwise.
- New config surfaced (tunable, mirroring the refund-cap / embedding pattern): provider
  fallback order + retry bound, `SEMANTIC_CACHE_*` (enabled, threshold, TTLs). Keys stay in
  the gitignored `.env`.
- Deferred (seams in place, not blocking): a per-user/personalized cache tier (explicitly
  out of scope — would need partitioning, low real hit-rate, reintroduces leakage risk);
  a real seller-approval publish workflow for merchandising drafts (draft persists; the
  publish action is a future story); cross-encoder rerank still identity v0 (ADR-0033).
