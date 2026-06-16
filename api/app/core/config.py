"""Application settings (Pydantic v2, env-driven).

No secrets live in code. `DATABASE_URL` and `EMBED_DIM` come from the environment
(see repo-root `.env.example`). `EMBED_DIM` is the pgvector embedding dimension —
Echo owns the final value; we default to 768 (Gemini text-embedding-004) so a fresh
DB migrates today. See docs/decisions/0018-uuidv7-and-pgvector-dim.md.

`CORS_ORIGINS` is the browser allow-list for the API. It defaults to the local web
dev origin and accepts a comma-separated env override (`HEARTH_CORS_ORIGINS`). Origins
are not secrets, so the example value is fine to commit.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Backend configuration, populated from the process environment."""

    # Load a gitignored `.env` (the human supplies real keys there) while keeping
    # process-env override precedence; `extra="ignore"` so unrelated compose vars
    # (POSTGRES_*, WEB_PORT, ...) don't trip validation. Bare `DATABASE_URL`/`EMBED_DIM`
    # still resolve from the environment exactly as before.
    # ``populate_by_name`` so aliased fields (``cors_origins`` / ``llm_fallback_order``)
    # accept their Python field name in a direct ``Settings(...)`` construction (tests),
    # while the env still binds via the alias (``HEARTH_CORS_ORIGINS`` / ``LLM_FALLBACK_ORDER``).
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", populate_by_name=True
    )

    # Postgres connection string. For local dev docker-compose derives this from
    # the POSTGRES_* vars; tooling (Alembic) reads it straight from the env.
    database_url: str = "postgresql+psycopg://postgres:CHANGE_ME@localhost:5432/agentic_ecommerce"

    # pgvector embedding dimension. ECHO COORDINATION POINT: change this to the
    # dimension of the model Echo standardizes on, then re-run the embeddings
    # migration. Default 768 = Gemini text-embedding-004.
    embed_dim: int = 768

    # Embedding PROVIDER selector. ECHO COORDINATION POINT (Week-4, ADR-0026):
    # the live embedding model is still an open human decision tied to the
    # free-tier Groq/Gemini key. Until that lands, "stub" selects the
    # deterministic, content-derived StubEmbedder so the seed + retrieval
    # plumbing are testable. Echo flips this to e.g. "gemini" (one env/config
    # change) once a real provider is registered in app/services/embeddings.py.
    embed_provider: str = "stub"

    # Embedding MODEL name for the hosted Gemini provider (US-E5-04b, ADR-0032). Only
    # used when EMBED_PROVIDER=gemini; reuses `gemini_api_key`. As-built: a Day-15 live
    # smoke showed `gemini-embedding-001` serves on the free tier and `text-embedding-004`
    # is RETIRED (404 on v1beta, same fate as `gemini-1.5-flash` chat). So we ship
    # `gemini-embedding-001` with MRL truncation to `embed_dim` (768) — which matches the
    # vector(768) column + HNSW vector_cosine_ops index. MRL truncation un-normalizes, so
    # GeminiEmbedder L2-normalizes after truncation. ADR-0032 records the as-built choice.
    embed_model: str = "gemini-embedding-001"

    # Eval JUDGE selector (US-E7-00, ADR-0030). The RAGAS harness's LLM-judge metrics
    # (response relevancy, faithfulness) run behind a Judge seam. "deterministic"
    # selects the CI-safe lexical-overlap stub so the harness runs with NO LLM keys.
    # RECOMMENDED armed judge: "llm" — scores with the SAME free-tier provider as the
    # product runtime (Groq/Gemini via LLM_PROVIDER), so one free-tier key arms both the
    # app and the eval gate (NO paid Anthropic key needed). "claude" remains an optional
    # paid judge (separate Anthropic key). Both arm the floors; "deterministic" is a smoke.
    # Flip via EVAL_JUDGE; judges register in app/eval/judge.py::_JUDGES (fail-loud on typo).
    eval_judge: str = "deterministic"

    # Eval ANSWERER selector (US-E7-00). The judge metrics need an `answer` per golden
    # question; with no live agent runtime yet, "stub" selects the CI-safe stub
    # answerer (app/eval/answerer.py). Flip to the real agent answerer once it lands.
    eval_answerer: str = "stub"

    # Eval JUDGE model + key for the live Claude judge (US-QA-D16, ADR-0033 §3). Only used
    # when EVAL_JUDGE=claude (the human's LOCAL run that ARMS the RAGAS v1 numeric floors).
    # The eval judge is SEPARATE from the runtime product LLM (Groq/Gemini free-tier) and
    # is a paid, local-only concern — the key lives ONLY in the gitignored `.env`; CI has
    # none, so the gate falls back to the deterministic-stub SMOKE (floors do not hard-fail).
    eval_judge_model: str = "claude-opus-4-8"
    anthropic_api_key: str = ""

    # Free-tier LLM judge model override (US-E7-EJ, ADR-0033 §3 addendum). When
    # EVAL_JUDGE=llm the gate scores with the SAME runtime provider as the product
    # (Groq/Gemini, via app/agent/llm.py::get_chat_model -> LLM_PROVIDER) — one free-tier
    # key arms BOTH runtime and eval, so no paid Anthropic key is needed to arm the gate.
    # Empty -> use the provider's configured runtime model (groq_model/gemini_model);
    # set this only to score the eval on a DIFFERENT model than the runtime agents use.
    eval_llm_model: str = ""

    # ---- Refund / spend guardrail tiers (US-E5-06/07, ADR-0033) ------------- #
    # The support agent's `refund` action is gated by amount tiers, compared in MINOR
    # units (integer cents) against the captured payment the refund would touch:
    #   * <= REFUND_AUTO_CAP_MINOR              -> agent executes (outcome=applied)
    #   * (auto, REFUND_HITL_CAP_MINOR]         -> queued for a human (hitl_deferred)
    #   * >  REFUND_HITL_CAP_MINOR              -> hard refused (outcome=refused)
    # Defaults: $50 auto cap, $200 HITL ceiling. Tunable without a code change (mirrors
    # the embed/judge settings pattern). Owners may self-serve only within the auto cap.
    refund_auto_cap_minor: int = 5000
    refund_hitl_cap_minor: int = 20000

    # ---- Runtime PRODUCT LLM (US-E5-03/04/09, ADR-0031) --------------------- #
    # The chat model behind the product's own agents (shopping/support/merch). Both
    # Groq AND Gemini are configured; `llm_provider` flips between them with a SINGLE
    # config-line change (mirrors the embed/judge registry pattern — unknown provider
    # fails loud in app/agent/llm.py::get_chat_model). Groq is the default primary;
    # Gemini is the Day-17 fallback (US-E5-09, fallback chain not built yet). Keys come
    # from the gitignored `.env` (the human supplies them); CI has none and injects a
    # FakeListChatModel, so an empty key here is fine for tests.
    llm_provider: str = "groq"
    groq_api_key: str = ""
    gemini_api_key: str = ""
    # Current Groq free-tier model (2026-06). Llama 3.3 70B Versatile — solid tool-calling
    # + structured-output support, the default for intent classification + the agent loop.
    groq_model: str = "llama-3.3-70b-versatile"
    # Gemini fallback model — fast, free-tier, tool-calling capable. Uses the
    # `*-latest` alias: a live-key smoke (Day 15) showed `gemini-2.0-flash` carries a
    # 0 free-tier quota on a fresh AI-Studio key while `gemini-flash-latest` serves
    # (and `gemini-1.5-flash` is retired/404). Alias = pragmatic for free-tier; pin a
    # dated version if/when this account gets a paid quota.
    gemini_model: str = "gemini-flash-latest"

    # ---- Provider routing + fallback (US-E5-09, ADR-0034 §1) ---------------- #
    # Runtime failover on top of the `llm_provider` one-line swap. The PRIMARY is
    # `llm_provider`; this orders the fallback chain. Auto-cascade fires on TRANSIENT
    # failures ONLY (HTTP 429 / timeout / 5xx) after a bounded retry of the primary;
    # a domain/APIError/guardrail refusal NEVER falls back (it's a deterministic
    # outcome, surfaced straight through the canonical envelope). Both exhausted ->
    # a canonical `rate_limited` (429) envelope, never a raw exception. The list is a
    # comma-separated provider order; the first entry is normally `llm_provider`. The
    # retry bound is the number of attempts at the PRIMARY before cascading once to the
    # next provider in the chain. Mirrors the executor's bounded-retry posture (ADR-0029).
    llm_fallback_order: Annotated[list[str], NoDecode] = Field(
        default=["groq", "gemini"], validation_alias="LLM_FALLBACK_ORDER"
    )
    llm_primary_max_attempts: int = 2

    # ---- Semantic cache (US-E5-09, ADR-0034 §2) ----------------------------- #
    # A pgvector-backed, NON-PERSONALIZED response cache so repeated/similar prompts
    # skip the LLM round-trip. Cacheable surfaces ONLY: intent classification + grounded
    # policy-RAG answers (the never-cache list — shopping/tool-results/PII/refusals/HITL/
    # any injection-fired turn — is enforced in code, not config). Ordering is load-bearing
    # (ADR-0033): scan_for_injection -> cache lookup -> LLM -> cache store. Tunable like the
    # refund caps. Keys fold in provider+model+node_type+embed_provider+embed_dim (+store_id
    # for policy). A lookup failure degrades to a live LLM call, never an internal_error.
    semantic_cache_enabled: bool = True
    # Cosine similarity threshold for a real-embedder hit (HIGH — a paraphrase, not a topic
    # match; a false positive silently serves a wrong answer). Under EMBED_PROVIDER=stub the
    # cache falls back to EXACT normalized-prompt match (stub similarity is noise).
    semantic_cache_threshold: float = 0.95
    # TTL backstop (content-version invalidation is primary). Classifier entries live a day;
    # policy answers an hour (a policy edit also busts them via source-version invalidation).
    semantic_cache_classifier_ttl_s: int = 86_400
    semantic_cache_policy_ttl_s: int = 3_600

    # Browser CORS allow-list for the API. Defaults to the local Next.js dev origin;
    # override via `HEARTH_CORS_ORIGINS` as a comma-separated list of origins, e.g.
    # `HEARTH_CORS_ORIGINS=https://app.example.com,https://admin.example.com`.
    # `NoDecode` stops pydantic-settings from JSON-parsing the env value so our
    # comma-split validator below owns the parsing.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:3000"],
        alias="HEARTH_CORS_ORIGINS",
    )

    @field_validator("cors_origins", "llm_fallback_order", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        """Accept a comma-separated env string (or an already-parsed list)."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


settings = Settings()
