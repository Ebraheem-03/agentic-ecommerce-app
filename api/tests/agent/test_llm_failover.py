"""Provider routing + fallback — transient-only auto-cascade (US-E5-09, ADR-0034 §1).

KEY-FREE: the failover policy is exercised with FAKE provider runnables (no Groq/Gemini
key). Each fake is a tiny object with ``.invoke()`` / ``.with_structured_output()`` —
enough to drive ``FailoverChatModel`` and prove the cascade rules:

  * a forced TRANSIENT failure on the primary (after its bounded retry) cascades to the
    secondary, which serves the answer;
  * a DOMAIN error (``APIError``) on the primary NEVER falls back — it surfaces unchanged;
  * a NON-transient generic error never falls back either;
  * BOTH providers exhausted -> a canonical ``rate_limited`` (429) envelope, never a raw
    exception, never a fabricated answer.

This mirrors the brains Protocol seam: CI forces the error and asserts the cascade WITHOUT
real keys.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.agent.llm import (
    FailoverChatModel,
    build_failover,
    is_transient_provider_error,
)
from app.core.errors import APIError
from app.schemas.envelope import ErrorCode


class _RateLimit(Exception):
    """A fake provider rate-limit error carrying an HTTP 429 status."""

    status_code = 429


class _ServerError(Exception):
    status_code = 503


class _Fake:
    """A minimal provider runnable: returns a value, or raises a scripted error per call."""

    def __init__(self, *, returns: Any = None, raises: Exception | None = None) -> None:
        self._returns = returns
        self._raises = raises
        self.calls = 0

    def invoke(self, *_args: Any, **_kwargs: Any) -> Any:
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._returns

    # The brains call with_structured_output before invoke; proxy to self so the
    # FailoverChatModel's member transform is a no-op for these fakes.
    def with_structured_output(self, schema: Any, **kwargs: Any) -> _Fake:
        return self


# --------------------------------------------------------------------------- #
# Transient classification.                                                     #
# --------------------------------------------------------------------------- #
def test_rate_limit_and_5xx_and_timeout_are_transient() -> None:
    assert is_transient_provider_error(_RateLimit())
    assert is_transient_provider_error(_ServerError())
    assert is_transient_provider_error(TimeoutError("timed out"))
    assert is_transient_provider_error(Exception("Service temporarily unavailable"))


def test_apierror_and_plain_errors_are_not_transient() -> None:
    # A domain APIError is a deterministic outcome — never a provider hiccup.
    assert not is_transient_provider_error(
        APIError(status_code=403, code=ErrorCode.forbidden, message="nope")
    )
    # A generic error with no transient signal is treated as non-transient.
    assert not is_transient_provider_error(ValueError("bad arg"))


# --------------------------------------------------------------------------- #
# Cascade behavior.                                                             #
# --------------------------------------------------------------------------- #
def test_transient_primary_cascades_to_secondary() -> None:
    """Primary fails transient (every attempt) -> secondary serves the answer."""
    primary = _Fake(raises=_RateLimit())
    secondary = _Fake(returns="from-gemini")
    model = build_failover([primary, secondary], primary_max_attempts=2)

    assert model.invoke("hi") == "from-gemini"
    assert primary.calls == 2  # bounded retry of the primary
    assert secondary.calls == 1  # cascaded once to the fallback


def test_domain_error_never_falls_back() -> None:
    """An APIError on the primary surfaces unchanged — the secondary is never called."""
    domain = APIError(status_code=422, code=ErrorCode.validation_error, message="bad")
    primary = _Fake(raises=domain)
    secondary = _Fake(returns="should-not-be-used")
    model = build_failover([primary, secondary], primary_max_attempts=2)

    with pytest.raises(APIError) as exc:
        model.invoke("hi")
    assert exc.value.code is ErrorCode.validation_error
    assert primary.calls == 1  # NOT retried (domain error is definitive)
    assert secondary.calls == 0  # never cascaded


def test_non_transient_error_does_not_fall_back() -> None:
    """A generic non-transient error surfaces unchanged without cascading."""
    primary = _Fake(raises=ValueError("boom"))
    secondary = _Fake(returns="unused")
    model = build_failover([primary, secondary], primary_max_attempts=2)

    with pytest.raises(ValueError):
        model.invoke("hi")
    assert secondary.calls == 0


def test_both_exhausted_surfaces_rate_limited_envelope() -> None:
    """Every provider transient -> canonical rate_limited (429), never a raw exception."""
    primary = _Fake(raises=_RateLimit())
    secondary = _Fake(raises=_ServerError())
    model = build_failover([primary, secondary], primary_max_attempts=2)

    with pytest.raises(APIError) as exc:
        model.invoke("hi")
    assert exc.value.status_code == 429
    assert exc.value.code is ErrorCode.rate_limited
    assert primary.calls == 2
    assert secondary.calls == 1


def test_structured_output_proxies_to_every_member() -> None:
    """with_structured_output returns a FailoverModel that still cascades."""
    primary = _Fake(raises=_RateLimit())
    secondary = _Fake(returns="structured")
    model = build_failover([primary, secondary], primary_max_attempts=1)

    bound = model.with_structured_output(object)
    assert isinstance(bound, FailoverChatModel)
    assert bound.invoke("hi") == "structured"
    assert primary.calls == 1  # primary_max_attempts=1 -> one try then cascade
