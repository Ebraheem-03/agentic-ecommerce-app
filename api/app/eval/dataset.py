"""Golden-eval dataset loader — typed records over ``golden-v0.jsonl`` (US-E7-00).

Centralises the JSONL parsing the retrieval smoke currently inlines, and gives the
harness a typed, validated record so downstream scorers never index into raw dicts.

Record schema mirrors ``docs/qa/eval/README.md``:
    id, question, expected_answer, source_docs[], tags, notes

``source_docs`` keys resolve against the live seeded DB by the same scheme the smoke
uses (``product`` slug / ``variant`` sku / ``policy`` ``<kind>@<store|platform>``); this
module keeps them typed but does NOT touch the DB — resolution is the scorers' job.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# api/app/eval/dataset.py -> parents[3] == repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]
GOLDEN_V0 = REPO_ROOT / "docs" / "qa" / "eval" / "golden-v0.jsonl"

SourceDocType = Literal["product", "variant", "policy"]


class SourceDoc(BaseModel):
    """One machine-checkable reference into the seed (a gold context).

    ``type`` selects the natural key scheme; ``key`` is the stable key:
    product slug / variant sku / policy ``<kind>@<store_slug|platform>``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: SourceDocType
    key: str = Field(min_length=1)


class EvalTags(BaseModel):
    """The controlled-vocab tags on a golden record.

    ``expects_refusal`` is the behavioural signal the harness surfaces beyond the
    numeric scores (a faithful answer to such an item must decline, not fabricate).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    persona: str
    category: str
    difficulty: str
    expects_refusal: bool


class GoldenRecord(BaseModel):
    """One typed golden eval record (a RAGAS sample's ground truth half).

    ``expected_answer`` is the RAGAS ``ground_truth``; ``source_docs`` are the gold
    ``contexts`` a faithful answer must rest on.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    expected_answer: str = Field(min_length=1)
    source_docs: list[SourceDoc] = Field(min_length=1)
    tags: EvalTags
    notes: str = ""


def iter_golden_lines(path: Path | None = None) -> Iterator[dict[str, object]]:
    """Stream raw JSON objects from a JSONL file, skipping blank lines.

    The single definition of "parse the golden JSONL" — the retrieval smoke can adopt
    this instead of re-inlining the loop. Kept dict-typed so non-pydantic callers (the
    smoke's set-overlap math) need not pull in the model.
    """
    src = path or GOLDEN_V0
    with src.open(encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                obj = json.loads(stripped)
                if not isinstance(obj, dict):
                    raise ValueError(f"golden record is not a JSON object: {stripped!r}")
                yield obj


def load_golden(path: Path | None = None) -> list[GoldenRecord]:
    """Load + validate the golden set into typed :class:`GoldenRecord`s.

    Raises ``pydantic.ValidationError`` on any malformed record (missing field, unknown
    key, empty string) so the harness fails loud rather than scoring garbage.
    """
    return [GoldenRecord.model_validate(obj) for obj in iter_golden_lines(path)]
