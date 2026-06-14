"""Tool DEFINITION tests — schema generation + parsing + serializable spec (US-E5-01).

LAYER SPLIT: these are Echo's unit-level checks on the tool registry itself — every
tool's input model generates a JSON schema, valid example args parse, invalid args
raise, and the provider-agnostic spec serializes. Juno owns the comprehensive per-tool
behavioral E2E matrix in US-QA-D12; these stay at the schema boundary.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.agent.tools import REGISTRY, ToolName, tool_specs

# A valid example arg-set per tool — must parse against the tool's input model.
_VALID_EXAMPLES: dict[ToolName, dict[str, object]] = {
    ToolName.search: {"query": "mug", "limit": 5},
    ToolName.product_details: {"id_or_slug": "tide-pour-over-mug"},
    ToolName.inventory: {"product_id_or_slug": "tide-pour-over-mug"},
    ToolName.add_to_cart: {"variant_id": "11111111-1111-1111-1111-111111111111", "qty": 2},
    ToolName.apply_coupon: {"code": "WELCOME10", "subtotal_minor": 5000},
    ToolName.draft_order: {"ship_address": {"recipient_name": "Ada", "line1": "1 St"}},
    ToolName.order_status: {"order_id": "22222222-2222-2222-2222-222222222222"},
    ToolName.refund: {"order_id": "22222222-2222-2222-2222-222222222222"},
}

# A clearly-invalid arg-set per tool (wrong type / out of range / missing required).
_INVALID_EXAMPLES: dict[ToolName, dict[str, object]] = {
    ToolName.search: {"query": "", "limit": 5},  # empty query (min_length=1)
    ToolName.product_details: {"id_or_slug": ""},  # empty (min_length=1)
    ToolName.inventory: {},  # missing required product_id_or_slug
    ToolName.add_to_cart: {"variant_id": "x", "qty": 0},  # qty < 1
    ToolName.apply_coupon: {"code": "X", "subtotal_minor": -1},  # negative subtotal
    ToolName.draft_order: {},  # missing required ship_address
    ToolName.order_status: {"order_id": "x", "extra": "nope"},  # extra forbidden
    ToolName.refund: {"order_id": ""},  # empty order_id
}


def test_registry_has_all_eight_tools() -> None:
    assert set(REGISTRY) == set(ToolName)
    assert len(REGISTRY) == 8


@pytest.mark.parametrize("name", list(ToolName))
def test_each_tool_json_schema_generates(name: ToolName) -> None:
    """``params_schema()`` (model_json_schema) generates and is a JSON object schema."""
    schema = REGISTRY[name].params_schema()
    assert isinstance(schema, dict)
    assert schema["type"] == "object"
    # ``extra="forbid"`` => additionalProperties is False on every tool input.
    assert schema.get("additionalProperties") is False


@pytest.mark.parametrize("name", list(ToolName))
def test_valid_example_args_parse(name: ToolName) -> None:
    parsed = REGISTRY[name].input_model.model_validate(_VALID_EXAMPLES[name])
    assert parsed is not None


@pytest.mark.parametrize("name", list(ToolName))
def test_invalid_example_args_raise(name: ToolName) -> None:
    with pytest.raises(ValidationError):
        REGISTRY[name].input_model.model_validate(_INVALID_EXAMPLES[name])


def test_provider_spec_is_serializable() -> None:
    """The provider-agnostic spec set round-trips through JSON (no provider leak)."""
    specs = tool_specs()
    assert len(specs) == 8
    blob = json.dumps(specs)  # must be JSON-serializable
    restored = json.loads(blob)
    names = {s["name"] for s in restored}
    assert names == {n.value for n in ToolName}
    for spec in restored:
        assert set(spec) == {"name", "description", "parameters"}
        assert spec["description"]
        assert spec["parameters"]["type"] == "object"


def test_mutating_and_sensitive_flags() -> None:
    """Flag wiring the executor depends on: mutate set + the single sensitive tool."""
    mutating = {n for n, s in REGISTRY.items() if s.mutating}
    sensitive = {n for n, s in REGISTRY.items() if s.sensitive}
    assert mutating == {ToolName.add_to_cart, ToolName.draft_order, ToolName.refund}
    assert sensitive == {ToolName.refund}
    # read_only is the inverse of mutating.
    assert REGISTRY[ToolName.search].read_only is True
    assert REGISTRY[ToolName.refund].read_only is False
