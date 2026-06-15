"""Chat-model factory — provider-swappable Groq | Gemini (US-E5-03/04, ADR-0031).

The product's agents (shopping/support/merch) talk to ONE chat model, resolved here by
``settings.llm_provider``. Both providers are configured; flipping ``LLM_PROVIDER``
(one config line) switches between them — Groq is the default primary, Gemini is the
Day-17 fallback (US-E5-09; the fallback *chain* is not built here, just the provider).

The factory mirrors the established registry seams (``get_embedder`` /
``get_retriever`` / ``_JUDGES``): a closed ``_PROVIDERS`` map, fail-loud on an unknown
provider. No business logic, no agent loop — just "give me a configured chat model".

**Injectability (the CI contract).** Every graph node takes its chat model as an
argument; nothing imports a module-level singleton. CI has no provider key, so tests
pass a ``FakeListChatModel`` / a stub instead of calling ``get_chat_model()``. This
module is therefore only exercised live when a real key is present (the human's smoke).
"""

from __future__ import annotations

from collections.abc import Callable

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import SecretStr

from app.core.config import Settings, settings


def _make_groq(cfg: Settings) -> BaseChatModel:
    """Groq chat model (default primary). Free-tier, strong tool-calling."""
    from langchain_groq import ChatGroq

    if not cfg.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to the gitignored .env (or switch "
            "LLM_PROVIDER), or inject a fake chat model in tests."
        )
    # temperature=0 for deterministic routing/structured-output; api_key is read from
    # the env by ChatGroq, but we pass it explicitly so the resolved settings win.
    return ChatGroq(
        model=cfg.groq_model, api_key=SecretStr(cfg.groq_api_key), temperature=0.0
    )


def _make_gemini(cfg: Settings) -> BaseChatModel:
    """Gemini chat model (Day-17 fallback — US-E5-09)."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    if not cfg.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to the gitignored .env (or switch "
            "LLM_PROVIDER), or inject a fake chat model in tests."
        )
    return ChatGoogleGenerativeAI(
        model=cfg.gemini_model,
        google_api_key=SecretStr(cfg.gemini_api_key),
        temperature=0.0,
    )


# Closed provider registry. Unknown provider -> fail loud (mirrors get_embedder).
_PROVIDERS: dict[str, Callable[[Settings], BaseChatModel]] = {
    "groq": _make_groq,
    "gemini": _make_gemini,
}


def get_chat_model(cfg: Settings | None = None) -> BaseChatModel:
    """Resolve the configured chat model for the product's agents.

    ``settings.llm_provider`` selects the provider; an unknown value raises (no silent
    default). Pass ``cfg`` to override the global settings (tests rarely need to — they
    inject a fake model into the graph directly rather than calling this).
    """
    cfg = cfg or settings
    factory = _PROVIDERS.get(cfg.llm_provider)
    if factory is None:
        known = ", ".join(sorted(_PROVIDERS))
        raise RuntimeError(
            f"Unknown LLM_PROVIDER {cfg.llm_provider!r}. Known providers: {known}."
        )
    return factory(cfg)


__all__ = ["get_chat_model"]
