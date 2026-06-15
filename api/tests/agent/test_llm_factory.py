"""LLM provider factory — Groq | Gemini swap + fail-loud + failover (US-E5-03/09, ADR-0031/0034).

No live call: asserts the registry behaviour (provider selection, fail-loud on unknown,
fail-loud on a missing key) WITHOUT constructing a real client where a key is absent.
Since US-E5-09 (ADR-0034 §1) ``get_chat_model`` returns a ``FailoverChatModel`` over the
configured chain (primary + LLM_FALLBACK_ORDER); a single-entry chain isolates one provider.
"""

from __future__ import annotations

import pytest

from app.agent.llm import FailoverChatModel, get_chat_model
from app.core.config import Settings


def test_unknown_provider_fails_loud() -> None:
    cfg = Settings(llm_provider="not-a-provider", llm_fallback_order=["not-a-provider"])
    with pytest.raises(RuntimeError, match="Unknown LLM provider"):
        get_chat_model(cfg)


def test_groq_missing_key_fails_loud() -> None:
    cfg = Settings(llm_provider="groq", groq_api_key="", llm_fallback_order=["groq"])
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        get_chat_model(cfg)


def test_gemini_missing_key_fails_loud() -> None:
    cfg = Settings(
        llm_provider="gemini", gemini_api_key="", llm_fallback_order=["gemini"]
    )
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        get_chat_model(cfg)


def test_groq_default_is_primary() -> None:
    """Default provider is Groq with the documented free-tier model."""
    cfg = Settings()
    assert cfg.llm_provider == "groq"
    assert cfg.groq_model == "llama-3.3-70b-versatile"


def test_get_chat_model_returns_failover_over_a_single_provider() -> None:
    """A present key resolves a FailoverChatModel wrapping the (single) provider chain."""
    cfg = Settings(
        llm_provider="groq", groq_api_key="test-key-not-real", llm_fallback_order=["groq"]
    )
    model = get_chat_model(cfg)
    assert isinstance(model, FailoverChatModel)


def test_get_chat_model_builds_the_full_failover_chain() -> None:
    """With both providers in the chain, construction needs BOTH keys (no network call)."""
    cfg = Settings(
        llm_provider="groq",
        groq_api_key="test-key-not-real",
        gemini_api_key="test-key-not-real",
        llm_fallback_order=["groq", "gemini"],
    )
    model = get_chat_model(cfg)
    assert isinstance(model, FailoverChatModel)
