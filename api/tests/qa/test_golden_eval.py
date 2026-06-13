"""Validator for the golden eval dataset v0 (US-QA-D05).

Two layers:

1. **Static well-formedness** (always runs, no DB): the dataset is exactly 25 records,
   ids are unique + non-empty, required fields present, tags come from a controlled
   vocabulary, and there's at least one refusal item.
2. **Seed-resolve** (DB-backed, skips without a live Postgres): reuse Sable's
   ``migration_db`` throwaway-DB fixture, migrate to head, run the seed, then assert
   **every** ``source_docs`` entry resolves to a real seeded row. This is what stops
   the golden set from silently drifting away from the seed.

Embedding-agnostic on purpose: nothing here touches vectors / EMBED_DIM (Echo's).
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session

import app.core.config as app_config
from alembic import command
from app.db.models import Policy, Product, Store, Variant
from app.db.seed.run import seed

# Repo-root-relative path to the dataset. This file: api/tests/qa/test_golden_eval.py
# -> parents[3] == repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]
DATASET = REPO_ROOT / "docs" / "qa" / "eval" / "golden-v0.jsonl"

EXPECTED_COUNT = 25
MIN_REFUSALS = 3

REQUIRED_FIELDS = ("id", "question", "expected_answer", "source_docs", "tags")

VALID_PERSONAS = {"buyer", "seller", "support", "admin"}
VALID_CATEGORIES = {
    "catalog",
    "inventory",
    "reviews",
    "returns",
    "shipping",
    "payments",
    "care",
    "policy",
}
VALID_DIFFICULTIES = {"direct", "multi-fact", "combine"}
VALID_SOURCE_TYPES = {"product", "variant", "policy"}
# Mirrors the policy_kind enum in app/db/models/_shared.py.
VALID_POLICY_KINDS = {"returns", "shipping", "payments", "care", "platform"}


def _load() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with DATASET.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                raise AssertionError(f"line {lineno}: invalid JSON: {exc}") from exc
    return records


# --------------------------------------------------------------------------- static


def test_dataset_exists() -> None:
    assert DATASET.is_file(), f"golden dataset missing at {DATASET}"


def test_count_and_unique_ids() -> None:
    records = _load()
    assert len(records) == EXPECTED_COUNT, f"expected {EXPECTED_COUNT}, got {len(records)}"
    ids = [r["id"] for r in records]
    assert all(isinstance(i, str) and i.strip() for i in ids), "every id must be non-empty"
    assert len(set(ids)) == len(ids), "ids must be unique"


def test_required_fields_present_and_nonempty() -> None:
    for r in _load():
        rid = r.get("id", "<no-id>")
        for field in REQUIRED_FIELDS:
            assert field in r, f"{rid}: missing field {field!r}"
        assert isinstance(r["question"], str) and r["question"].strip(), f"{rid}: empty question"
        assert (
            isinstance(r["expected_answer"], str) and r["expected_answer"].strip()
        ), f"{rid}: empty expected_answer"
        assert (
            isinstance(r["source_docs"], list) and r["source_docs"]
        ), f"{rid}: source_docs must be a non-empty list"


def test_tags_controlled_vocabulary() -> None:
    for r in _load():
        rid = r["id"]
        tags = r["tags"]
        assert tags["persona"] in VALID_PERSONAS, f"{rid}: bad persona {tags.get('persona')!r}"
        assert (
            tags["category"] in VALID_CATEGORIES
        ), f"{rid}: bad category {tags.get('category')!r}"
        assert (
            tags["difficulty"] in VALID_DIFFICULTIES
        ), f"{rid}: bad difficulty {tags.get('difficulty')!r}"
        assert isinstance(
            tags["expects_refusal"], bool
        ), f"{rid}: expects_refusal must be bool"


def test_source_docs_shape() -> None:
    for r in _load():
        rid = r["id"]
        for ref in r["source_docs"]:
            assert set(ref) >= {"type", "key"}, f"{rid}: source_doc needs type+key"
            assert ref["type"] in VALID_SOURCE_TYPES, f"{rid}: bad source type {ref['type']!r}"
            assert isinstance(ref["key"], str) and ref["key"].strip(), f"{rid}: empty key"
            if ref["type"] == "policy":
                assert "@" in ref["key"], f"{rid}: policy key must be '<kind>@<store|platform>'"
                kind = ref["key"].split("@", 1)[0]
                assert kind in VALID_POLICY_KINDS, f"{rid}: bad policy kind {kind!r}"


def test_combine_items_have_multiple_sources() -> None:
    for r in _load():
        if r["tags"]["difficulty"] == "combine":
            assert (
                len(r["source_docs"]) >= 2
            ), f"{r['id']}: 'combine' difficulty must cite >=2 source_docs"


def test_minimum_refusal_coverage() -> None:
    refusals = [r for r in _load() if r["tags"]["expects_refusal"]]
    assert len(refusals) >= MIN_REFUSALS, (
        f"need >= {MIN_REFUSALS} refusal items (faithfulness = not fabricating); "
        f"got {len(refusals)}"
    )


# --------------------------------------------------------------------- seed-resolve


def _sqla_url(dsn: str) -> str:
    return (
        make_url(dsn).set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
    )


def test_every_source_doc_resolves_against_seed(migration_db: tuple[Config, str]) -> None:
    """Migrate + seed a throwaway DB, then assert every source_docs ref is real.

    This is the anti-drift guarantee: if a SKU/slug/policy is renamed or removed from
    the seed, this fails until the golden set is updated.
    """
    cfg, dsn = migration_db
    command.upgrade(cfg, "head")
    importlib.reload(app_config)

    engine = create_engine(_sqla_url(dsn), future=True)
    try:
        with Session(engine) as s:
            seed(s)
            s.commit()

        with Session(engine) as s:
            product_slugs = set(s.scalars(select(Product.slug)))
            variant_skus = set(s.scalars(select(Variant.sku)))
            # (kind, store_slug-or-None) tuples for every seeded policy.
            policy_rows = s.execute(
                select(Policy.kind, Store.slug).join(
                    Store, Policy.store_id == Store.id, isouter=True
                )
            ).all()
            policy_keys: set[tuple[str, str | None]] = {
                (kind, store_slug) for kind, store_slug in policy_rows
            }

        missing: list[str] = []
        for r in _load():
            for ref in r["source_docs"]:
                kind, key = ref["type"], ref["key"]
                if kind == "product" and key not in product_slugs:
                    missing.append(f"{r['id']}: product slug {key!r} not in seed")
                elif kind == "variant" and key not in variant_skus:
                    missing.append(f"{r['id']}: variant sku {key!r} not in seed")
                elif kind == "policy":
                    pk, scope = key.split("@", 1)
                    store_slug = None if scope == "platform" else scope
                    if (pk, store_slug) not in policy_keys:
                        missing.append(f"{r['id']}: policy {key!r} not in seed")

        assert not missing, "golden set drifted from seed:\n" + "\n".join(missing)
    finally:
        engine.dispose()
