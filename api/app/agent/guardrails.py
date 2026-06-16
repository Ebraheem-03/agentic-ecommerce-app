"""Guardrails — injection defense, refund tiering, output validation (US-E5-07, ADR-0033).

This module is the policy layer the support agent + executor consult. It has three parts:

1. REFUND / SPEND TIERS (ADR-0033 §1). ``refund_tier(amount_minor)`` maps the captured
   payment amount the refund would touch to one of three outcomes, compared in MINOR units
   (integer cents) against config caps:
     * <= REFUND_AUTO_CAP_MINOR              -> AUTO   (agent executes; outcome=applied)
     * (auto, REFUND_HITL_CAP_MINOR]         -> HITL   (queued for a human; hitl_deferred)
     * >  REFUND_HITL_CAP_MINOR              -> REFUSE (hard refused; outcome=refused)
   The caps are config (tunable). This is the concrete tier logic the ADR-0029
   ``_check_scope`` / refund-path seam was reserved for.

2. INJECTION DEFENSE (ADR-0033 §2): strict boundary + detect + log + refuse. Untrusted
   content — USER turns AND retrieved RAG passages (product copy, policy prose, reviews) —
   is DATA, never instructions. The structural guarantee (identity/scope/refund-tier can
   NEVER be set by LLM output or retrieved text) is already enforced upstream: the acting
   ``User``/``Session``/``conversation_id`` are closed over from request context, never read
   from model output or retrieved text (``langchain_tools`` / ``GraphDeps``). On top of that
   structural guarantee, ``scan_for_injection`` detects injection PATTERNS (instruction
   override, fake system/tool framing, tool-call smuggling, prompt exfiltration, cap-lift
   attempts) so the agent can refuse + log them as signal.

3. OUTPUT VALIDATION: ``validate_grounding`` checks that a grounded (non-refusal) answer
   actually cites real retrieved sources — a structural check that the answer isn't
   ungrounded prose.

Everything here is PURE + deterministic (no LLM, no key) so it gates in CI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from app.core.config import settings


# --------------------------------------------------------------------------- #
# 1. Refund / spend tiers.                                                      #
# --------------------------------------------------------------------------- #
class RefundTier(StrEnum):
    """The autonomy tier a refund amount falls into (ADR-0033 §1)."""

    auto = "auto"
    hitl = "hitl"
    refuse = "refuse"


def refund_tier(amount_minor: int) -> RefundTier:
    """Classify a refund amount (MINOR units) into its autonomy tier.

    Boundaries: inclusive at the auto cap ($50), inclusive at the HITL ceiling ($200),
    strictly above the ceiling is refused. Caps come from config so they're tunable.
    """
    if amount_minor <= settings.refund_auto_cap_minor:
        return RefundTier.auto
    if amount_minor <= settings.refund_hitl_cap_minor:
        return RefundTier.hitl
    return RefundTier.refuse


# --------------------------------------------------------------------------- #
# 2. Injection defense — detect, then the caller logs + refuses.               #
# --------------------------------------------------------------------------- #
class InjectionKind(StrEnum):
    """The category of prompt-injection an untrusted span matched."""

    instruction_override = "instruction_override"
    fake_system = "fake_system"
    tool_smuggling = "tool_smuggling"
    prompt_exfiltration = "prompt_exfiltration"
    cap_lift = "cap_lift"


@dataclass(frozen=True, slots=True)
class InjectionHit:
    """A matched injection pattern — what kind + the offending span (for the audit log)."""

    kind: InjectionKind
    span: str


# Pattern table. Each entry is (kind, compiled regex). Patterns are intentionally narrow —
# they target imperative attempts to RE-INSTRUCT the agent, not ordinary mentions of the
# words (e.g. "what is your return policy" must NOT trip ``prompt_exfiltration``). Case-
# insensitive; matched against user turns AND retrieved passages alike.
_PATTERNS: tuple[tuple[InjectionKind, re.Pattern[str]], ...] = (
    (
        InjectionKind.instruction_override,
        re.compile(
            r"\b(ignore|disregard|forget|override)\b.{0,40}?"
            r"\b(previous|prior|above|earlier|all)\b.{0,20}?"
            r"\b(instruction|prompt|rule|direction|message)s?\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        InjectionKind.instruction_override,
        # "new instructions:", "from now on you must", "you are now ..."
        re.compile(
            r"\b(new instructions?|from now on|you are now|act as)\b",
            re.IGNORECASE,
        ),
    ),
    (
        InjectionKind.fake_system,
        # Fake role/turn framing smuggled into content (chat-markup injection).
        re.compile(
            r"(<\|?(system|im_start|im_end)\|?>|\[/?(system|inst)\]|^\s*system\s*:)",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        InjectionKind.tool_smuggling,
        # Attempts to make the model emit a tool/function call directly from content.
        re.compile(
            r"\b(call|invoke|execute|run)\b.{0,20}?\b(tool|function|refund|draftorder)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        InjectionKind.prompt_exfiltration,
        re.compile(
            r"\b(reveal|repeat|print|show|leak|expose)\b.{0,30}?"
            r"\b(system|developer)?\s*(prompt|instructions?|rules?)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        InjectionKind.cap_lift,
        # Attempts to talk the agent past the refund cap / approval requirement.
        re.compile(
            r"\b(ignore|bypass|raise|lift|remove|exceed|skip)\b.{0,30}?"
            r"\b(cap|limit|threshold|approval|hitl|review)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
)


def scan_for_injection(*texts: str) -> InjectionHit | None:
    """Return the FIRST injection pattern matched across ``texts``, else None.

    Scans every supplied untrusted span (user turn + each retrieved passage). The first
    hit is enough to refuse + log — we don't need an exhaustive list, just the signal that
    untrusted content tried to re-instruct the agent.
    """
    for text in texts:
        if not text:
            continue
        for kind, pattern in _PATTERNS:
            match = pattern.search(text)
            if match is not None:
                span = match.group(0).strip()
                return InjectionHit(kind=kind, span=span[:200])
    return None


INJECTION_REFUSAL = (
    "I can't follow instructions embedded in a message or document — I only act on your "
    "direct request through the supported actions. Let me know what you'd like to do and "
    "I'll help within what I'm allowed to do."
)


# --------------------------------------------------------------------------- #
# 3. Output validation — grounded answers must cite real retrieved sources.    #
# --------------------------------------------------------------------------- #
def validate_grounding(*, is_refusal: bool, cited_source_ids: list[str]) -> bool:
    """A non-refusal grounded answer MUST cite at least one real retrieved source.

    Returns True if the output is well-formed: a refusal needs no citation; a substantive
    grounded answer must reference at least one retrieved source row. The caller passes the
    source ids actually returned by retrieval, so this can't be satisfied by invented ids.
    """
    if is_refusal:
        return True
    return len(cited_source_ids) > 0


__all__ = [
    "INJECTION_REFUSAL",
    "InjectionHit",
    "InjectionKind",
    "RefundTier",
    "refund_tier",
    "scan_for_injection",
    "validate_grounding",
]
