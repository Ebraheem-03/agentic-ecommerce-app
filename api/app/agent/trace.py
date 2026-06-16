"""Local structured trace store — per-agent-run observability (US-E7-04, ADR-0042 §D1).

WHAT THIS IS
============
A SELF-CONTAINED, key-free observability substrate for the product's LangGraph runtime.
Every agent turn produces ONE :class:`RunTrace` recording:

  * ``trace_id`` / ``run_id`` / ``conversation_id`` (the thread) / ``route``;
  * per-NODE spans (classify / shopping / support / merchandising / checkout / ...),
    each with its own latency;
  * each TOOL call the executor ran (name, a compact args summary, the outcome);
  * each MODEL call (the prompt sent, ``tokens_in`` / ``tokens_out``, ``cost_usd``,
    ``latency_ms``) — token usage read from the LangChain response
    ``usage_metadata`` / ``response_metadata`` where available, ``None`` otherwise;
  * the final DISPOSITION (reply / clarify / refusal / checkout-proposed / fallback).

Traces are written to ``docs/qa/obs/results/<run>.jsonl`` (gitignored, the same convention
as the eval/agent artifacts) — **no external SaaS, no API key, no prompt/PII off-box**, so
the key-free CI invariant holds. A dormant LangSmith seam sits behind ONE env flag
(``OBS_BACKEND=local|langsmith``); only the local path is active and there is NO langsmith
hard-dependency — selecting ``langsmith`` logs once and degrades to local.

WHY A CONTEXTVAR (ambient current trace)
========================================
The graph nodes and the executor are called by LangGraph with a fixed ``(state, config)``
signature; threading a trace handle through every node + the executor would touch a lot of
surface. Instead the runner opens a trace for the turn and binds it to a
:data:`contextvars.ContextVar`; nodes/executor write to it through the tiny module-level
helpers (:func:`node_span`, :func:`record_tool_call`, :func:`record_model_call`). When no
trace is active (e.g. a direct unit test of a node) every helper is a NO-OP. Tracing is
**best-effort throughout**: every write is wrapped so a tracing fault NEVER breaks a turn.
"""

from __future__ import annotations

import contextvars
import json
import logging
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import settings

_log = logging.getLogger(__name__)

# api/app/agent/trace.py -> parents[3] == repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "docs" / "qa" / "obs" / "results"


# --------------------------------------------------------------------------- #
# Per-provider/model price table (USD per 1M tokens). Free-tier -> 0.0, but the #
# field + the table are MODELLED so a paid model would compute a real cost.     #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class _Price:
    """USD per 1,000,000 tokens, split input vs output (free-tier rows are 0.0)."""

    input_per_mtok: float
    output_per_mtok: float


# Keyed by ``provider:model``; falls back to a provider-level ``provider:*`` row, then 0.0.
# Groq + Gemini free-tier are 0.0 today; the structure lets a paid row drop in unchanged.
_PRICE_TABLE: dict[str, _Price] = {
    "groq:*": _Price(0.0, 0.0),
    "groq:llama-3.3-70b-versatile": _Price(0.0, 0.0),
    "gemini:*": _Price(0.0, 0.0),
    "gemini:gemini-flash-latest": _Price(0.0, 0.0),
    "gemini:gemini-2.0-flash": _Price(0.0, 0.0),
    # Example PAID row (not active) — shows the table computes a real cost when one exists.
    "anthropic:claude-opus-4-8": _Price(15.0, 75.0),
}


def estimate_cost(
    provider: str, model: str, tokens_in: int | None, tokens_out: int | None
) -> float:
    """USD cost for a model call from the price table (0.0 for free-tier / unknown rows).

    Looks up ``provider:model``, then the provider wildcard ``provider:*``, then 0.0.
    Missing token counts (scripted brains / no usage metadata) contribute 0 — the field is
    still modelled so a paid model with real usage would compute a non-zero cost.
    """
    price = _PRICE_TABLE.get(f"{provider}:{model}") or _PRICE_TABLE.get(f"{provider}:*")
    if price is None:
        return 0.0
    cost = (
        (tokens_in or 0) / 1_000_000 * price.input_per_mtok
        + (tokens_out or 0) / 1_000_000 * price.output_per_mtok
    )
    return round(cost, 8)


def extract_usage(response: Any) -> tuple[int | None, int | None]:
    """Best-effort (tokens_in, tokens_out) from a LangChain response.

    Reads ``usage_metadata`` (the modern field: ``input_tokens`` / ``output_tokens``) first,
    then ``response_metadata['token_usage']`` (provider-specific:
    ``prompt_tokens`` / ``completion_tokens``). Returns ``(None, None)`` when usage is absent
    — e.g. a scripted brain or a structured-output object with no metadata. NEVER raises.
    """
    try:
        usage = getattr(response, "usage_metadata", None)
        if isinstance(usage, dict):
            return usage.get("input_tokens"), usage.get("output_tokens")
        meta = getattr(response, "response_metadata", None)
        if isinstance(meta, dict):
            tu = meta.get("token_usage") or meta.get("usage")
            if isinstance(tu, dict):
                return (
                    tu.get("prompt_tokens") or tu.get("input_tokens"),
                    tu.get("completion_tokens") or tu.get("output_tokens"),
                )
    except Exception:  # noqa: BLE001 - tracing is best-effort, never break a turn
        _log.debug("trace: usage extraction failed", exc_info=True)
    return None, None


# --------------------------------------------------------------------------- #
# Trace record types.                                                          #
# --------------------------------------------------------------------------- #
@dataclass
class NodeSpan:
    """One graph-node execution: its name + wall-clock latency."""

    name: str
    latency_ms: float = 0.0


@dataclass
class ToolCallTrace:
    """One executor tool call: name, a compact args summary, and the outcome."""

    name: str
    args_summary: str
    outcome: str  # applied | refused | hitl_deferred | error | blocked


@dataclass
class ModelCallTrace:
    """One chat-model invocation: which node/provider, the prompt, tokens, cost, latency."""

    node: str
    provider: str
    model: str
    prompt: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float = 0.0
    latency_ms: float = 0.0


@dataclass
class RunTrace:
    """The full trace for one agent turn (one row in the JSONL store)."""

    trace_id: str
    run_id: str
    conversation_id: str | None
    route: str | None = None
    disposition: str | None = None
    started_at: str = ""
    latency_ms: float = 0.0
    node_spans: list[NodeSpan] = field(default_factory=list)
    tool_calls: list[ToolCallTrace] = field(default_factory=list)
    model_calls: list[ModelCallTrace] = field(default_factory=list)
    # Internal: monotonic start, not serialized.
    _t0: float = field(default=0.0, repr=False)

    @property
    def tokens_in(self) -> int:
        return sum(m.tokens_in or 0 for m in self.model_calls)

    @property
    def tokens_out(self) -> int:
        return sum(m.tokens_out or 0 for m in self.model_calls)

    @property
    def cost_usd(self) -> float:
        return round(sum(m.cost_usd for m in self.model_calls), 8)

    def to_record(self) -> dict[str, Any]:
        """Serialize to a JSON-able dict (rolls up token/cost totals for the consumer)."""
        data = asdict(self)
        data.pop("_t0", None)
        data["tokens_in"] = self.tokens_in
        data["tokens_out"] = self.tokens_out
        data["cost_usd"] = self.cost_usd
        return data


# Ambient current trace for the turn (None outside a traced run -> helpers no-op).
_current_trace: contextvars.ContextVar[RunTrace | None] = contextvars.ContextVar(
    "current_agent_trace", default=None
)


def current_trace() -> RunTrace | None:
    """The trace bound to this turn, or ``None`` (every write helper tolerates ``None``)."""
    return _current_trace.get()


def _args_summary(args: dict[str, Any], *, limit: int = 200) -> str:
    """A compact, PII-light one-line summary of tool args for the trace."""
    try:
        text = json.dumps(args, sort_keys=True, default=str)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        text = repr(args)
    return text if len(text) <= limit else text[: limit - 1] + "…"


# --------------------------------------------------------------------------- #
# Write helpers — all best-effort (a tracing fault never breaks a turn).        #
# --------------------------------------------------------------------------- #
@contextmanager
def node_span(name: str) -> Iterator[None]:
    """Time a graph node and record a :class:`NodeSpan` on the current trace (if any).

    A no-op (still yields) when no trace is active or tracing is disabled. The span is
    recorded even if the node raises — the latency up to the fault is useful signal.
    """
    trace = _current_trace.get()
    if trace is None:
        yield
        return
    t0 = time.perf_counter()
    try:
        yield
    finally:
        try:
            trace.node_spans.append(
                NodeSpan(name=name, latency_ms=round((time.perf_counter() - t0) * 1000, 3))
            )
        except Exception:  # noqa: BLE001 - best-effort
            _log.debug("trace: node span record failed", exc_info=True)


def record_tool_call(name: str, args: dict[str, Any], outcome: str) -> None:
    """Record one executor tool call on the current trace (best-effort, no-op if none)."""
    trace = _current_trace.get()
    if trace is None:
        return
    try:
        trace.tool_calls.append(
            ToolCallTrace(name=name, args_summary=_args_summary(args), outcome=outcome)
        )
    except Exception:  # noqa: BLE001 - best-effort
        _log.debug("trace: tool call record failed", exc_info=True)


def record_model_call(
    *,
    node: str,
    provider: str,
    model: str,
    prompt: str,
    response: Any = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    latency_ms: float = 0.0,
) -> None:
    """Record one model invocation on the current trace (best-effort, no-op if none).

    If ``response`` is given, token usage is read from it via :func:`extract_usage` unless
    ``tokens_in`` / ``tokens_out`` are passed explicitly. Cost comes from the price table.
    """
    trace = _current_trace.get()
    if trace is None:
        return
    try:
        if response is not None and tokens_in is None and tokens_out is None:
            tokens_in, tokens_out = extract_usage(response)
        trace.model_calls.append(
            ModelCallTrace(
                node=node,
                provider=provider,
                model=model,
                prompt=prompt if len(prompt) <= 4000 else prompt[:3999] + "…",
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=estimate_cost(provider, model, tokens_in, tokens_out),
                latency_ms=round(latency_ms, 3),
            )
        )
    except Exception:  # noqa: BLE001 - best-effort
        _log.debug("trace: model call record failed", exc_info=True)


def set_route(route: str | None) -> None:
    """Record the classifier's route on the current trace (best-effort, no-op if none)."""
    trace = _current_trace.get()
    if trace is not None and route is not None:
        trace.route = route


def set_disposition(disposition: str) -> None:
    """Record the turn's final disposition on the current trace (best-effort, no-op)."""
    trace = _current_trace.get()
    if trace is not None:
        trace.disposition = disposition


# --------------------------------------------------------------------------- #
# Trace lifecycle — open / bind / emit. Driven by the runner per turn.          #
# --------------------------------------------------------------------------- #
@contextmanager
def trace_turn(
    *, conversation_id: str | None, run_id: str | None = None
) -> Iterator[RunTrace | None]:
    """Open a trace for one turn, bind it as the current trace, and emit it on exit.

    Yields the live :class:`RunTrace` (or ``None`` when ``OBS_ENABLED`` is false — tracing
    is then a pure no-op and the turn runs unchanged). The trace is emitted to the
    configured backend on exit even if the turn raised, so a failing turn still leaves a
    trace. The whole lifecycle is best-effort: any tracing fault is swallowed.
    """
    if not settings.obs_enabled:
        yield None
        return
    trace = RunTrace(
        trace_id=uuid.uuid4().hex,
        run_id=run_id or uuid.uuid4().hex,
        conversation_id=conversation_id,
        started_at=datetime.now(UTC).isoformat(),
        _t0=time.perf_counter(),
    )
    token = _current_trace.set(trace)
    try:
        yield trace
    finally:
        try:
            trace.latency_ms = round((time.perf_counter() - trace._t0) * 1000, 3)
            emit_trace(trace)
        except Exception:  # noqa: BLE001 - emitting a trace never breaks the turn
            _log.warning("trace: emit failed", exc_info=True)
        finally:
            _current_trace.reset(token)


def emit_trace(trace: RunTrace, *, results_dir: Path | None = None) -> Path | None:
    """Emit a finished trace via the configured backend; return the JSONL path (local).

    ``OBS_BACKEND=local`` (default) appends the trace as one line to
    ``docs/qa/obs/results/<run>.jsonl``. ``OBS_BACKEND=langsmith`` is a DORMANT seam: there
    is no langsmith dependency, so it logs once and degrades to the local writer (the trace
    is never lost). Best-effort: returns ``None`` on any failure.
    """
    backend = settings.obs_backend.lower()
    if backend == "langsmith":
        _log.info(
            "trace: OBS_BACKEND=langsmith is a dormant seam (no hosted dep wired); "
            "writing locally instead."
        )
    elif backend != "local":
        _log.warning("trace: unknown OBS_BACKEND %r — writing locally.", backend)
    return _write_local(trace, results_dir=results_dir)


def _write_local(trace: RunTrace, *, results_dir: Path | None = None) -> Path | None:
    """Append the trace as one JSON line to the per-run JSONL file (gitignored)."""
    try:
        out_dir = results_dir or RESULTS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{trace.run_id}.jsonl"
        line = json.dumps(trace.to_record(), default=str) + "\n"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
        return path
    except Exception:  # noqa: BLE001 - best-effort
        _log.warning("trace: local write failed", exc_info=True)
        return None


__all__ = [
    "ModelCallTrace",
    "NodeSpan",
    "RunTrace",
    "ToolCallTrace",
    "current_trace",
    "emit_trace",
    "estimate_cost",
    "extract_usage",
    "node_span",
    "record_model_call",
    "record_tool_call",
    "set_disposition",
    "set_route",
    "trace_turn",
]
