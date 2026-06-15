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
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
    # NOTE: the eval judge is SEPARATE from the runtime PRODUCT LLM (Groq/Gemini
    # free-tier) — per CLAUDE.md it may be Claude. Flip to e.g. "claude" once a real
    # judge is registered in app/eval/judge.py::_JUDGES (defaults to claude-opus-4-8).
    eval_judge: str = "deterministic"

    # Eval ANSWERER selector (US-E7-00). The judge metrics need an `answer` per golden
    # question; with no live agent runtime yet, "stub" selects the CI-safe stub
    # answerer (app/eval/answerer.py). Flip to the real agent answerer once it lands.
    eval_answerer: str = "stub"

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

    # Browser CORS allow-list for the API. Defaults to the local Next.js dev origin;
    # override via `HEARTH_CORS_ORIGINS` as a comma-separated list of origins, e.g.
    # `HEARTH_CORS_ORIGINS=https://app.example.com,https://admin.example.com`.
    # `NoDecode` stops pydantic-settings from JSON-parsing the env value so our
    # comma-split validator below owns the parsing.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:3000"],
        alias="HEARTH_CORS_ORIGINS",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Accept a comma-separated env string (or an already-parsed list)."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


settings = Settings()
