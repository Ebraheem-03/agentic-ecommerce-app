"""Agent runtime layer (the product's own agents) — tools + executor (US-E5-01/02).

SCOPE: this package is the *tool layer* only — typed tool definitions (input/output
schemas + a provider-agnostic registry) and a callable executor (validation, auth
scope, idempotency, bounded retry, audit). It does NOT contain the SSE agent loop or
the orchestrator/reasoning agent; those land later and will sit alongside this package.

Provider-agnostic on purpose: no Groq/Gemini specifics leak in here. The registry
exposes each tool's spec (name + description + JSON schema of params) shaped for LLM
function-calling, but the layer itself is just typed defs + a dispatcher.
"""

from __future__ import annotations

from app.agent.tools import REGISTRY, ToolName, tool_specs

__all__ = [
    "REGISTRY",
    "ToolName",
    "tool_specs",
]
