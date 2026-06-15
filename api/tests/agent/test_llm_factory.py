"""LLM provider factory — Groq | Gemini swap + fail-loud (US-E5-03, ADR-0031).

No live call: asserts the registry behaviour (provider selection, fail-loud on unknown,
fail-loud on a missing key) WITHOUT constructing a real client where a key is absent.
"""

from __future__ import annotations

import pytest

from app.agent.llm import get_chat_model
from app.core.config import Settings


def test_unknown_provider_fails_loud() -> None:
    cfg = Settings(llm_provider="not-a-provider")
    with pytest.raises(RuntimeError, match="Unknown LLM_PROVIDER"):
        get_chat_model(cfg)


def test_groq_missing_key_fails_loud() -> None:
    cfg = Settings(llm_provider="groq", groq_api_key="")
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        get_chat_model(cfg)


def test_gemini_missing_key_fails_loud() -> None:
    cfg = Settings(llm_provider="gemini", gemini_api_key="")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        get_chat_model(cfg)


def test_groq_default_is_primary() -> None:
    """Default provider is Groq with the documented free-tier model."""
    cfg = Settings()
    assert cfg.llm_provider == "groq"
    assert cfg.groq_model == "llama-3.3-70b-versatile"


def test_groq_provider_constructs_with_key() -> None:
    """A present key resolves a Groq chat model (no network on construction)."""
    cfg = Settings(llm_provider="groq", groq_api_key="test-key-not-real")
    model = get_chat_model(cfg)
    assert model.__class__.__name__ == "ChatGroq"


def test_gemini_provider_constructs_with_key() -> None:
    cfg = Settings(llm_provider="gemini", gemini_api_key="test-key-not-real")
    model = get_chat_model(cfg)
    assert model.__class__.__name__ == "ChatGoogleGenerativeAI"
