"""Chat-model factory + provider failover — Groq | Gemini (US-E5-03/04/09, ADR-0031/0034).

The product's agents (shopping/support/merch) talk to ONE chat model, resolved here by
``settings.llm_provider``. Both providers are configured; flipping ``LLM_PROVIDER``
(one config line) selects the PRIMARY. On top of that, US-E5-09 (ADR-0034 §1) adds
**runtime failover**: if the primary fails on a TRANSIENT error (HTTP 429 / timeout /
5xx) after a bounded retry, the call cascades ONCE to the next provider in
``LLM_FALLBACK_ORDER``. Both exhausted -> a canonical ``rate_limited`` (429) envelope,
never a raw exception, never a fabricated answer.

DOMAIN errors never trigger fallback. An ``APIError`` / validation / guardrail refusal is
a deterministic outcome, not a provider hiccup — it surfaces straight through unchanged
(re-running it on the other provider would mask a real bug + double latency).

CENTRAL WRAP (no per-node duplication). The failover wraps the chat-model invocation
ONCE, around ``get_chat_model()``. ``get_chat_model()`` returns a ``FailoverChatModel``
that proxies ``with_structured_output`` / ``bind_tools`` to each underlying provider and,
on ``.invoke()``, runs the bounded-retry-then-cascade policy. All three brains call the
model the same way they already do (``model.with_structured_output(X).invoke(...)``), so
they inherit failover with no code change.

**Injectability (the CI contract).** Every graph node takes its chat model as an
argument; nothing imports a module-level singleton. CI has no provider key, so tests
pass a fake model / a stub brain instead of calling ``get_chat_model()``. The failover
policy itself is testable key-free: ``build_failover`` accepts already-constructed
provider runnables, so a test can pass a fake that raises a forced transient and assert
the cascade WITHOUT a real key (mirrors the brains Protocol seam).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any, Protocol, runtime_checkable

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import SecretStr

from app.core.config import Settings, settings
from app.core.errors import APIError
from app.schemas.envelope import ErrorCode

_log = logging.getLogger(__name__)


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


# --------------------------------------------------------------------------- #
# Transient-vs-domain classification (ADR-0034 §1).                            #
# --------------------------------------------------------------------------- #
# HTTP status codes that mean "provider hiccup, safe to fail over": rate-limit + 5xx.
_TRANSIENT_STATUSES = frozenset({429, 500, 502, 503, 504})


def is_transient_provider_error(exc: BaseException) -> bool:
    """Classify a chat-model exception as a TRANSIENT provider failure (-> may fail over).

    Transient = rate-limit (429), timeout, or 5xx from the provider — a provider hiccup,
    not a deterministic outcome. We inspect, in order:

      * an explicit ``APIError`` is a DOMAIN error -> never transient (never fails over);
      * a ``TimeoutError`` is transient;
      * a status code carried on the exception (``status_code`` / ``http_status`` /
        ``code``, or a nested ``response.status_code``) in the transient set;
      * a textual signal (``rate limit`` / ``429`` / ``timeout`` / ``503`` / ``overloaded``
        / ``temporarily unavailable``) — provider SDKs vary, so the message is a backstop.

    Anything else is treated as NON-transient (surfaces unchanged) — we only fail over when
    we have positive evidence of a transient fault, so a real bug isn't masked by a retry.
    """
    if isinstance(exc, APIError):
        return False
    if isinstance(exc, TimeoutError):
        return True
    status = _status_of(exc)
    if status is not None:
        return status in _TRANSIENT_STATUSES
    text = str(exc).lower()
    signals = (
        "rate limit",
        "ratelimit",
        "429",
        "timeout",
        "timed out",
        "503",
        "502",
        "overloaded",
        "temporarily unavailable",
        "service unavailable",
    )
    return any(s in text for s in signals)


def _status_of(exc: BaseException) -> int | None:
    """Best-effort HTTP status extraction from a provider SDK exception."""
    for attr in ("status_code", "http_status", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    if response is not None:
        value = getattr(response, "status_code", None)
        if isinstance(value, int):
            return value
    return None


def _providers_unavailable() -> APIError:
    """Canonical envelope when every provider in the chain is exhausted (ADR-0034 §1)."""
    return APIError(
        status_code=429,
        code=ErrorCode.rate_limited,
        message=(
            "The assistant is briefly over capacity. Please try again in a moment."
        ),
    )


# --------------------------------------------------------------------------- #
# Failover wrapper — proxies structured-output / tool binding, cascades on      #
# transient errors at .invoke() time.                                           #
# --------------------------------------------------------------------------- #
@runtime_checkable
class ChatRunnable(Protocol):
    """The minimal chat-model surface ``FailoverChatModel`` wraps.

    A ``BaseChatModel`` (and its ``with_structured_output`` / ``bind_tools`` derivatives)
    satisfies this; so does a test fake — which is why CI drives the failover key-free.
    """

    def invoke(self, *args: Any, **kwargs: Any) -> Any: ...

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any: ...


class FailoverChatModel:
    """A chat model that fails over across providers on transient errors (ADR-0034 §1).

    Wraps an ORDERED list of provider runnables (each is a ``BaseChatModel`` or a
    runnable derived from one via ``with_structured_output`` / ``bind_tools``). On
    ``.invoke()`` it tries the FIRST provider up to ``primary_max_attempts`` times on a
    transient error, then cascades ONCE to each subsequent provider (one attempt each).
    The first NON-transient exception surfaces immediately (domain errors never fail
    over). Exhausting every provider -> a canonical ``rate_limited`` (429) ``APIError``.

    ``with_structured_output`` / ``bind_tools`` return a NEW ``FailoverChatModel`` whose
    members are each underlying provider with the same transform applied — so a brain that
    calls ``model.with_structured_output(IntentResult).invoke(...)`` gets failover across
    BOTH providers' structured-output runnables with no brain change.
    """

    def __init__(
        self, members: Sequence[ChatRunnable], *, primary_max_attempts: int = 2
    ) -> None:
        if not members:
            raise ValueError("FailoverChatModel needs at least one provider runnable.")
        self._members: tuple[ChatRunnable, ...] = tuple(members)
        self._primary_max_attempts = max(1, primary_max_attempts)

    def with_structured_output(self, schema: Any, **kwargs: Any) -> FailoverChatModel:
        return FailoverChatModel(
            [m.with_structured_output(schema, **kwargs) for m in self._members],
            primary_max_attempts=self._primary_max_attempts,
        )

    def bind_tools(self, tools: Any, **kwargs: Any) -> FailoverChatModel:
        return FailoverChatModel(
            [m.bind_tools(tools, **kwargs) for m in self._members],  # type: ignore[attr-defined]
            primary_max_attempts=self._primary_max_attempts,
        )

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        """Invoke with bounded-retry-then-cascade across the provider chain.

        The first provider is retried up to ``primary_max_attempts`` on a transient error;
        each later provider gets ONE attempt. A non-transient exception surfaces at once.
        All providers exhausted -> ``rate_limited`` (429). A failover is logged as signal.
        """
        last_transient: BaseException | None = None
        for index, member in enumerate(self._members):
            attempts = self._primary_max_attempts if index == 0 else 1
            for attempt in range(1, attempts + 1):
                try:
                    return member.invoke(*args, **kwargs)
                except APIError:
                    raise  # domain outcome — never fail over (would mask a real bug)
                except Exception as exc:  # noqa: BLE001 - classify then decide
                    if not is_transient_provider_error(exc):
                        raise  # non-transient -> surface unchanged
                    last_transient = exc
                    _log.warning(
                        "chat provider %d/%d transient failure (attempt %d/%d): %s",
                        index + 1,
                        len(self._members),
                        attempt,
                        attempts,
                        exc,
                    )
            # primary retries exhausted (or this fallback failed) — cascade to the next.
        raise _providers_unavailable() from last_transient


def build_failover(
    members: Sequence[ChatRunnable],
    *,
    primary_max_attempts: int | None = None,
) -> FailoverChatModel:
    """Assemble a ``FailoverChatModel`` from pre-built provider runnables (test seam).

    Key-free: a test passes fakes (e.g. one raising a forced transient, one returning a
    value) to assert the cascade WITHOUT a provider key — mirroring the brains Protocol
    seam. ``primary_max_attempts`` defaults to the configured bound.
    """
    bound = (
        settings.llm_primary_max_attempts
        if primary_max_attempts is None
        else primary_max_attempts
    )
    return FailoverChatModel(members, primary_max_attempts=bound)


def get_chat_model(cfg: Settings | None = None) -> FailoverChatModel:
    """Resolve the configured chat model (with provider failover) for the agents.

    ``settings.llm_provider`` selects the PRIMARY; ``settings.llm_fallback_order`` orders
    the failover chain (the primary is moved to the front if not already there). Returns a
    ``FailoverChatModel`` so every brain inherits transient-only failover with no per-node
    change. An unknown provider in the chain fails loud (no silent default).

    Each provider is constructed LAZILY only as it enters the chain — but since failover
    needs all members up front, construction here requires every chained provider's key.
    A single-provider chain (``LLM_FALLBACK_ORDER`` = one entry) needs only that key.
    """
    cfg = cfg or settings
    order = _resolve_chain(cfg)
    members: list[ChatRunnable] = []
    for name in order:
        factory = _PROVIDERS.get(name)
        if factory is None:
            known = ", ".join(sorted(_PROVIDERS))
            raise RuntimeError(
                f"Unknown LLM provider {name!r} in the fallback chain. Known: {known}."
            )
        members.append(factory(cfg))
    return FailoverChatModel(members, primary_max_attempts=cfg.llm_primary_max_attempts)


def _resolve_chain(cfg: Settings) -> list[str]:
    """The provider order: primary first, then the configured fallbacks (de-duplicated)."""
    chain: list[str] = [cfg.llm_provider]
    for name in cfg.llm_fallback_order:
        if name not in chain:
            chain.append(name)
    return chain


__all__ = [
    "FailoverChatModel",
    "build_failover",
    "get_chat_model",
    "is_transient_provider_error",
]
