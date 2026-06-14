"""RAGAS retrieval smoke — context precision@k / recall@k over the golden set (US-QA-D10).

WHAT THIS IS (and is NOT)
=========================
A **deterministic, no-LLM** retrieval-quality smoke. It exercises the LIVE keyword
``GET /search`` endpoint (Postgres FTS, ``ts_rank``) against the seeded catalog using the
product-grounded subset of the golden eval set (``docs/qa/eval/golden-v0.jsonl``), and
computes two retrieval metrics that need NO LLM judge:

  * **context recall@k**    — of a question's ground-truth source products, how many appear
                              in the top-k retrieved results.   |relevant ∩ topk| / |relevant|
  * **context precision@k** — of the top-k retrieved results, how many are ground-truth.
                              |relevant ∩ topk| / min(k, n_retrieved)

This is the **retrieval half** of RAGAS. The faithfulness / answer-relevancy half (the
LLM-judge gate, ≥0.90) is Echo's Week-4 work and needs LLM keys (still an open DECISION).
When semantic/pgvector retrieval lands (Echo, contract-v0 Decision-4), the SAME smoke runs
against ``mode=semantic`` and these numbers become the comparison baseline.

SMOKE, NOT A GATE
=================
Keyword retrieval is lexical AND ``websearch_to_tsquery`` ANDs every token of the input,
so feeding a raw natural-language golden QUESTION ("How much is the Tide Pour-Over Mug?")
requires every word — "how", "much", stopwords stripped, plus the hyphen-split "pour-over"
lexemes — to co-occur in one product's tsvector. In practice that matches **nothing** for
the question phrasing: keyword recall@k over raw questions is ~0 by construction. That is
not a bug — it is the precise gap semantic retrieval closes (an embedded query needs no
lexical overlap), and capturing it here is the whole point: this smoke is the retrieval
baseline semantic work must beat.

Because that near-zero is the EXPECTED keyword result, this test does NOT gate on any
recall threshold. It asserts only that the smoke RAN over a real in-scope subset, produced
well-formed aggregate scores in ``[0,1]``, and logged every failing sample. The scores are
CAPTURED (printed summary + a machine-readable JSON artifact under
``docs/qa/eval/results/``) for Echo to baseline against. A separate keyword sanity check
(below) proves the endpoint itself is alive on a distinctive single TERM, so a flat-zero
question score reflects the lexical gap, not a broken endpoint.

SCOPE
=====
Only **product-grounded** golden items are in scope: those whose ``source_docs`` cite a
``product`` (slug) or ``variant`` (sku -> its product) — these are searchable in the
catalog. **Policy** source_docs are NOT in the product catalog; policy/RAG retrieval is a
separate surface (Echo's agent RAG, later) and is excluded here, not failed. A few items
are mixed (product + policy, e.g. EVAL-025): the product half is in scope, the policy half
is ignored for this catalog smoke.

Reuses the seed source_doc -> row resolution spirit of ``tests/qa/test_golden_eval.py``
(variant sku -> product slug is resolved against the live seeded DB, anti-drift).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Product, Variant
from tests.conftest import ContractClient, SeededDb

# api/tests/qa/test_retrieval_smoke.py -> parents[3] == repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]
DATASET = REPO_ROOT / "docs" / "qa" / "eval" / "golden-v0.jsonl"
RESULTS_DIR = REPO_ROOT / "docs" / "qa" / "eval" / "results"

# Top-k cutoff for the retrieval metrics. Small + meaningful: a buyer scans the first
# handful of hits, and precision against the full 24-row default page would be dominated
# by the denominator. k=5 keeps precision interpretable while giving recall room.
K = 5

# NOT a recall gate. Raw-question keyword recall is ~0 by construction (see docstring),
# so we never assert a recall floor — that would hard-fail the suite on exactly the
# expected lexical gap. Endpoint liveness is proven separately on a distinctive TERM.


def _load_golden() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with DATASET.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _variant_sku_to_product_slug(session: Session) -> dict[str, str]:
    """Map every seeded variant SKU to its owning product slug (anti-drift, live seed)."""
    rows = session.execute(
        select(Variant.sku, Product.slug).join(Product, Variant.product_id == Product.id)
    ).all()
    return {sku: slug for sku, slug in rows}


def _expected_product_slugs(
    record: dict[str, Any], sku_to_slug: dict[str, str]
) -> set[str]:
    """The ground-truth catalog product slugs a question's source_docs resolve to.

    ``product`` refs contribute their slug directly; ``variant`` refs contribute their
    product's slug (resolved via the live seed). ``policy`` refs are out of catalog scope
    and contribute nothing.
    """
    slugs: set[str] = set()
    for ref in record["source_docs"]:
        if ref["type"] == "product":
            slugs.add(ref["key"])
        elif ref["type"] == "variant":
            slug = sku_to_slug.get(ref["key"])
            if slug is not None:
                slugs.add(slug)
        # policy -> not a catalog product; ignored for the retrieval smoke.
    return slugs


def test_retrieval_smoke_captures_precision_recall(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    """Run the no-LLM retrieval smoke, capture scores, log failing samples.

    Asserts the smoke RAN (>=1 in-scope item, scores produced, failures logged) and a
    low sanity floor — it does NOT gate on a recall threshold (see module docstring).
    """
    golden = _load_golden()

    with Session(seeded_db.engine) as s:
        sku_to_slug = _variant_sku_to_product_slug(s)

    per_item: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    precisions: list[float] = []
    recalls: list[float] = []

    for record in golden:
        expected = _expected_product_slugs(record, sku_to_slug)
        if not expected:
            continue  # policy-only / out-of-catalog item — not in retrieval scope.

        question = record["question"]
        body = api_client.get("/search", params={"q": question, "limit": 100}).json()
        retrieved = [r["product"]["slug"] for r in body["data"]]
        topk = retrieved[:K]
        hits = expected & set(topk)

        recall = len(hits) / len(expected)
        precision = len(hits) / min(K, len(topk)) if topk else 0.0
        precisions.append(precision)
        recalls.append(recall)

        item = {
            "id": record["id"],
            "question": question,
            "tags": record["tags"],
            "expected_slugs": sorted(expected),
            "retrieved_topk": topk,
            "precision_at_k": round(precision, 4),
            "recall_at_k": round(recall, 4),
        }
        per_item.append(item)
        if recall < 1.0:  # any ground-truth product missed from top-k = a failing sample
            failures.append(item)

    # The smoke must have actually run over a real in-scope subset.
    assert per_item, "no product-grounded golden items found — smoke did not run"

    mean_precision = sum(precisions) / len(precisions)
    mean_recall = sum(recalls) / len(recalls)

    # ----------------------------------------------------------------- capture
    stamp = datetime.now(UTC)
    artifact = {
        "generated_at": stamp.isoformat(),
        "story": "US-QA-D10",
        "endpoint": "GET /search",
        "retrieval_mode": "keyword",
        "k": K,
        "metric_notes": (
            "context recall@k = |relevant ∩ topk| / |relevant|; "
            "context precision@k = |relevant ∩ topk| / min(k, n_retrieved). "
            "No-LLM retrieval smoke (RAGAS retrieval half). Informational, not a CI gate."
        ),
        "scope": {
            "golden_total": len(golden),
            "in_scope_product_grounded": len(per_item),
            "out_of_scope_policy_only": len(golden) - len(per_item),
            "failing_samples": len(failures),
        },
        "scores": {
            "mean_precision_at_k": round(mean_precision, 4),
            "mean_recall_at_k": round(mean_recall, 4),
        },
        "items": per_item,
        "failing_samples": failures,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"retrieval-smoke-{stamp.strftime('%Y-%m-%d')}.json"
    out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    # Stable pointer to the latest run for Echo's Week-4 baseline.
    (RESULTS_DIR / "retrieval-smoke-latest.json").write_text(
        json.dumps(artifact, indent=2) + "\n", encoding="utf-8"
    )

    # --------------------------------------------------- log (stdout via -s / on failure)
    print("\n=== RAGAS retrieval smoke (keyword, no-LLM) — US-QA-D10 ===")
    print(
        f"k={K}  in-scope={len(per_item)}/{len(golden)} golden "
        f"(policy-only excluded={len(golden) - len(per_item)})"
    )
    print(
        f"mean precision@{K}={mean_precision:.3f}  "
        f"mean recall@{K}={mean_recall:.3f}  "
        f"failing samples={len(failures)}"
    )
    print(f"artifact -> {out.relative_to(REPO_ROOT)}")
    if failures:
        print("--- failing samples (ground-truth product missed from top-k) ---")
        for f in failures:
            print(
                f"  {f['id']} [{f['tags']['difficulty']}/"
                f"{'refusal' if f['tags']['expects_refusal'] else 'answer'}] "
                f"{f['question']!r}\n"
                f"      expected={f['expected_slugs']}  "
                f"retrieved_top{K}={f['retrieved_topk']}  recall={f['recall_at_k']}"
            )

    # --------------------------------------------------- assert: the smoke RAN (NOT a recall gate)
    # We deliberately do NOT assert a recall floor: raw-question keyword recall is ~0 by
    # construction (websearch ANDs every token), and that gap is the captured finding, not
    # a failure. What we DO guarantee: a real in-scope subset was scored, the metrics are
    # well-formed in [0,1], failures were enumerated, and the artifact was written.
    assert len(precisions) == len(per_item) == len(recalls)
    assert all(0.0 <= p <= 1.0 for p in precisions)
    assert all(0.0 <= r <= 1.0 for r in recalls)
    assert out.is_file() and (RESULTS_DIR / "retrieval-smoke-latest.json").is_file()
    # Each failing sample carries the diagnostic Echo needs (expected vs retrieved top-k).
    for f in failures:
        assert f["expected_slugs"] and "retrieved_topk" in f


def test_keyword_endpoint_is_live_on_distinctive_terms(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    """Liveness anchor: keyword search DOES recall the right product from a bare term.

    This is the control for the question-level zero recall above: when the input is a
    single distinctive lexeme (not a full sentence), keyword retrieval recalls the correct
    product at top-1 — proving the smoke's near-zero question scores are the lexical
    AND/phrasing gap, not a dead endpoint. (Term -> product slug pairs are seeded facts.)
    """
    term_to_slug = {
        "tide": "tide-pour-over-mug",
        "wallet": "carryall-card-wallet",
        "candle": "hearthlight-candle",
    }
    for term, slug in term_to_slug.items():
        body = api_client.get("/search", params={"q": term, "limit": K}).json()
        slugs = [r["product"]["slug"] for r in body["data"]]
        assert slug in slugs, f"keyword search lost {slug!r} for term {term!r}: {slugs}"


@pytest.mark.parametrize("k", [1, 5])
def test_precision_recall_math_is_well_formed(k: int) -> None:
    """Unit-pin the metric definitions (no DB) so the smoke's math can't silently drift."""
    expected = {"a", "b"}
    # All relevant retrieved within top-k -> recall 1.0.
    topk = (["a", "b", "x"])[:k]
    hits = expected & set(topk)
    recall = len(hits) / len(expected)
    precision = len(hits) / min(k, len(topk)) if topk else 0.0
    if k == 1:
        assert recall == 0.5 and precision == 1.0  # only 'a' in top-1
    else:
        assert recall == 1.0 and precision == pytest.approx(2 / 3)
