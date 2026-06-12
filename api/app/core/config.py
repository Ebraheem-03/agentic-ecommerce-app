"""Application settings (Pydantic v2, env-driven).

No secrets live in code. `DATABASE_URL` and `EMBED_DIM` come from the environment
(see repo-root `.env.example`). `EMBED_DIM` is the pgvector embedding dimension —
Echo owns the final value; we default to 768 (Gemini text-embedding-004) so a fresh
DB migrates today. See docs/decisions/0018-uuidv7-and-pgvector-dim.md.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Backend configuration, populated from the process environment."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    # Postgres connection string. For local dev docker-compose derives this from
    # the POSTGRES_* vars; tooling (Alembic) reads it straight from the env.
    database_url: str = "postgresql+psycopg://postgres:CHANGE_ME@localhost:5432/agentic_ecommerce"

    # pgvector embedding dimension. ECHO COORDINATION POINT: change this to the
    # dimension of the model Echo standardizes on, then re-run the embeddings
    # migration. Default 768 = Gemini text-embedding-004.
    embed_dim: int = 768


settings = Settings()
