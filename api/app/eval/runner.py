"""RAGAS runner — drive the harness over the golden set + write the score artifact.

This is the DB-aware orchestration layer. It:

1. resolves each golden record's ``source_docs`` to gold context KEYS against the live
   seeded DB (variant sku -> owning product slug; product slug / policy ``kind@store``
   pass through) — the same anti-drift spirit as ``test_golden_eval.py`` / the smoke;
2. gathers RETRIEVED contexts per record:
     * product-grounded items -> the live keyword ``GET /search`` (top-k product slugs +
       their embeddable documents as context texts), exactly as the retrieval smoke;
     * policy contexts are NOT yet a live retrieval surface (Echo's agent RAG, Week-4),
       so the policy half is recorded as out-of-retrieval-scope, not failed;
3. scores every record through :func:`app.eval.harness.score_record` on the active
   answerer + judge (deterministic by default);
4. writes a ``ragas-<date>.json`` + stable ``ragas-latest.json`` artifact under
   ``docs/qa/eval/results/`` (gitignored, like the smoke artifacts) carrying per-item
   scores, the four means, judge/answerer identity, scope counts, and the refusal log.

Retrieved-context resolution is injected as a callable so the harness stays testable
without a web client; the default uses the live ``GET /search`` via ``search_products``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Policy, Product, Store, Variant
from app.eval.answerer import Answerer, get_answerer
from app.eval.dataset import GOLDEN_V0, GoldenRecord, load_golden
from app.eval.harness import HarnessSummary, ItemResult, score_record, summarize
from app.eval.judge import Judge, get_judge
from app.services.embeddings import build_product_document
from app.services.search import get_retriever

# api/app/eval/runner.py -> parents[3] == repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "docs" / "qa" / "eval" / "results"

# Top-k retrieval cutoff — same small, interpretable window the smoke uses (k=5).
K = 5


class RetrievedContexts(Protocol):
    """Resolves the retrieved contexts for one record.

    Returns ``(keys, texts)``: the retrieved context KEYS (product slugs) for the
    precision/recall math, and the context TEXTS the judge reads for faithfulness.
    Injected so the harness is testable without a live retriever.
    """

    def __call__(
        self, record: GoldenRecord, session: Session
    ) -> tuple[list[str], list[str]]: ...


def _variant_sku_to_product_slug(session: Session) -> dict[str, str]:
    """Map every seeded variant SKU to its owning product slug (live seed, anti-drift)."""
    rows = session.execute(
        select(Variant.sku, Product.slug).join(Product, Variant.product_id == Product.id)
    ).all()
    return {sku: slug for sku, slug in rows}


def _policy_key_exists(session: Session, key: str) -> bool:
    """Resolve a ``<kind>@<store_slug|platform>`` policy key against the live seed."""
    kind, _, scope = key.partition("@")
    stmt = select(Policy.id).where(Policy.kind == kind)
    if scope == "platform":
        stmt = stmt.where(Policy.store_id.is_(None))
    else:
        store_id = session.scalar(select(Store.id).where(Store.slug == scope))
        if store_id is None:
            return False
        stmt = stmt.where(Policy.store_id == store_id)
    return session.scalar(stmt) is not None


def gold_context_keys(record: GoldenRecord, sku_to_slug: dict[str, str]) -> set[str]:
    """The gold context KEYS a record's ``source_docs`` resolve to.

    Product refs -> their slug; variant refs -> their product's slug (live seed); policy
    refs -> the ``kind@scope`` key verbatim. Mixed items contribute keys of every kind;
    the retrieval scoring only compares against the keys it can retrieve.
    """
    keys: set[str] = set()
    for ref in record.source_docs:
        if ref.type == "product":
            keys.add(ref.key)
        elif ref.type == "variant":
            slug = sku_to_slug.get(ref.key)
            if slug is not None:
                keys.add(slug)
        else:  # policy
            keys.add(ref.key)
    return keys


def product_gold_slugs(record: GoldenRecord, sku_to_slug: dict[str, str]) -> set[str]:
    """The catalog-product subset of a record's gold keys (excludes policy keys)."""
    slugs: set[str] = set()
    for ref in record.source_docs:
        if ref.type == "product":
            slugs.add(ref.key)
        elif ref.type == "variant":
            slug = sku_to_slug.get(ref.key)
            if slug is not None:
                slugs.add(slug)
    return slugs


def live_keyword_retrieval(record: GoldenRecord, session: Session) -> tuple[list[str], list[str]]:
    """Default retriever: top-k product slugs + documents from live keyword search.

    Mirrors the retrieval smoke — runs the live keyword ``Retriever`` over the record's
    raw question and returns the top-k product slugs (keys) plus each product's
    embeddable document (the context text the judge reads). Policy contexts are NOT a
    live retrieval surface yet (Week-4), so only product contexts are returned here.
    """
    retriever = get_retriever()  # live keyword path
    scored = retriever.retrieve(session, query=record.question, category=None, limit=100)
    topk = scored[:K]
    keys = [sp.product.slug for sp in topk]
    texts = [build_product_document(sp.product) for sp in topk]
    return keys, texts


def run_eval(
    session: Session,
    *,
    answerer: Answerer | None = None,
    judge: Judge | None = None,
    retrieve: RetrievedContexts | None = None,
    dataset_path: Path | None = None,
) -> tuple[list[ItemResult], HarnessSummary, dict[str, object]]:
    """Run the harness over the golden set; return (results, summary, scope-meta).

    Defaults to the active answerer/judge (deterministic, CI-safe) and the live keyword
    retrieval. Records every record (product- and policy-grounded), so the four metric
    means cover the whole set; the per-item evidence shows which contexts were
    retrievable vs out-of-(live-)retrieval-scope.
    """
    answerer = answerer or get_answerer()
    judge = judge or get_judge()
    retrieve = retrieve or live_keyword_retrieval

    golden = load_golden(dataset_path)
    sku_to_slug = _variant_sku_to_product_slug(session)

    results: list[ItemResult] = []
    policy_only = 0
    for record in golden:
        gold_keys = gold_context_keys(record, sku_to_slug)
        if not product_gold_slugs(record, sku_to_slug):
            policy_only += 1
        retrieved_keys, retrieved_texts = retrieve(record, session)
        results.append(
            score_record(
                record,
                gold_context_keys=gold_keys,
                retrieved_context_keys=retrieved_keys,
                retrieved_context_texts=retrieved_texts,
                answerer=answerer,
                judge=judge,
                k=K,
            )
        )

    summary = summarize(results)
    scope: dict[str, object] = {
        "golden_total": len(golden),
        "items_scored": len(results),
        "policy_only_no_live_retrieval": policy_only,
        "product_grounded": len(golden) - policy_only,
    }
    return results, summary, scope


def write_artifact(
    results: list[ItemResult],
    summary: HarnessSummary,
    scope: dict[str, object],
    *,
    answerer: Answerer,
    judge: Judge,
    results_dir: Path | None = None,
) -> Path:
    """Write the dated + ``ragas-latest.json`` score artifacts; return the dated path.

    Gitignored (``docs/qa/eval/results/ragas-*.json``), like the smoke artifacts, so the
    wall-clock-stamped file never churns CI. Carries per-item scores, the four means,
    judge/answerer identity (deterministic-vs-real distinguishable), scope counts, and
    the refusal log.
    """
    out_dir = results_dir or RESULTS_DIR
    stamp = datetime.now(UTC)
    refusal_log = [
        {
            "id": r.id,
            "expects_refusal": r.expects_refusal,
            "answer_refused": r.answer_refused,
        }
        for r in results
        if r.expects_refusal or r.answer_refused
    ]
    artifact: dict[str, object] = {
        "generated_at": stamp.isoformat(),
        "story": "US-E7-00",
        "harness": "ragas-style (deterministic default)",
        "judge": judge.identity,
        "answerer": answerer.identity,
        "k": K,
        "metric_notes": (
            "context precision/recall = set-overlap vs gold source_docs (no judge). "
            "response relevancy/faithfulness = Judge metrics; the DETERMINISTIC judge is "
            "a harness-exercising lexical stub, NOT a semantic judge — scores prove the "
            "pipeline ran + is well-formed, not answer quality. Real Claude judge is a "
            "one-line EVAL_JUDGE swap (see ADR-0030)."
        ),
        "scope": scope,
        "means": summary.model_dump(),
        "refusal_log": refusal_log,
        "items": [r.model_dump() for r in results],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(artifact, indent=2) + "\n"
    dated = out_dir / f"ragas-{stamp.strftime('%Y-%m-%d')}.json"
    dated.write_text(payload, encoding="utf-8")
    (out_dir / "ragas-latest.json").write_text(payload, encoding="utf-8")
    return dated


def main() -> None:  # pragma: no cover - manual CLI entry point
    """Manual entry point: run the eval against ``DATABASE_URL`` and write the artifact.

    ``python -m app.eval.runner`` (needs a live seeded DB). The CI-safe automated run is
    the pytest in ``tests/qa/test_ragas_harness.py``.
    """
    from sqlalchemy import create_engine

    from app.core.config import settings

    answerer = get_answerer()
    judge = get_judge()
    engine = create_engine(settings.database_url, future=True)
    try:
        with Session(engine) as session:
            results, summary, scope = run_eval(session, answerer=answerer, judge=judge)
        out = write_artifact(
            results, summary, scope, answerer=answerer, judge=judge
        )
    finally:
        engine.dispose()
    print(f"RAGAS harness (judge={judge.identity}, answerer={answerer.identity})")
    print(json.dumps(summary.model_dump(), indent=2))
    print(f"artifact -> {out.relative_to(REPO_ROOT)}  (dataset {GOLDEN_V0.name})")
