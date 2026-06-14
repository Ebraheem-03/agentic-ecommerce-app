"""Search E2E — the J-BUY-01 discovery journey end-to-end (US-QA-D10).

LAYER SPLIT (read before adding cases here)
===========================================
Orion's ``tests/api/test_search.py`` is the **endpoint-unit** layer: it pins the
contract atoms of ``GET /search`` in isolation — relevance ranking of one product,
``meta.mode``/per-result ``score`` shape, descending-score ordering, category-filter
narrowing, no-match -> empty 200, and the 422 validation envelope (empty / missing /
over-long ``q``, capped ``limit``). Those are NOT re-asserted here.

THIS module is the **journey/E2E** layer for **J-BUY-01** (the search journey from
``docs/qa/fixture-plan.md``): it chains the endpoints a buyer actually walks, against
the real ASGI app + the seeded throwaway DB (``seeded_db`` + ``api_client``):

  * search -> a search hit resolves to a real, fetchable product DETAIL page
    (the discovery -> PDP hand-off; the result's id/slug are not dangling).
  * refine — adding a second term narrows a broad result set (query refinement),
    and the kept results are a subset of the broad ones.
  * category facet within the journey — a buyer filtering the result list still
    lands on products that are individually fetchable and in that category.
  * the retrieval ``mode`` discriminator is stable across the journey (keyword today;
    the Decision-4 swap point Echo flips for semantic later).

The eval/retrieval-quality smoke over the golden set lives in
``tests/qa/test_retrieval_smoke.py`` — that is the RAGAS retrieval half, not here.
"""

from __future__ import annotations

from app.schemas.search import SearchMode
from tests.conftest import ContractClient, ResolvedHandles, SeededDb


# --------------------------------------------------------------------------- #
# search -> PDP hand-off: a hit is a real, fetchable product                   #
# --------------------------------------------------------------------------- #
def test_search_hit_resolves_to_fetchable_product_detail(
    seeded_db: SeededDb, api_client: ContractClient, handles: ResolvedHandles
) -> None:
    # A buyer searches a distinctive term and clicks the top hit -> the PDP loads.
    results = api_client.get("/search?q=tide").json()["data"]
    assert results, "expected a hit for 'tide'"
    top = results[0]["product"]
    assert top["id"] == handles.product_ids["mug"]

    # The discovery -> detail hand-off: the summary's id AND slug both resolve to the
    # same live ProductDetail (no dangling reference between the two surfaces).
    by_id = api_client.get(f"/products/{top['id']}")
    by_slug = api_client.get(f"/products/{top['slug']}")
    assert by_id.status_code == 200 and by_slug.status_code == 200
    detail = by_id.json()["data"]
    assert detail == by_slug.json()["data"]
    assert detail["slug"] == "tide-pour-over-mug"
    # The PDP carries the buy surface the journey continues into (variants to add).
    assert detail["variants"], "PDP reached from search must expose variants"


# --------------------------------------------------------------------------- #
# query refinement: a second term narrows, results stay a subset               #
# --------------------------------------------------------------------------- #
def test_refining_query_narrows_to_subset(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    # Broad term matches several products; refining with a second AND-term (websearch
    # ANDs space-separated terms) narrows to a strict subset of the broad result ids.
    broad_ids = [
        r["product"]["id"]
        for r in api_client.get("/search?q=serving&limit=100").json()["data"]
    ]
    assert len(broad_ids) >= 2, "expected a broad result set to refine from"

    refined_ids = [
        r["product"]["id"]
        for r in api_client.get("/search?q=serving+bowl&limit=100").json()["data"]
    ]
    assert refined_ids, "refinement should still match the bowl"
    assert set(refined_ids) <= set(broad_ids), "refined results must be a subset"
    assert len(refined_ids) < len(broad_ids), "refinement should narrow the set"


# --------------------------------------------------------------------------- #
# faceting within the journey: filtered hits are individually fetchable        #
# --------------------------------------------------------------------------- #
def test_category_faceted_hits_are_fetchable_and_in_category(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    body = api_client.get(
        "/search?q=serving+OR+wallet&category=Kitchen+%26+Dining&limit=100"
    ).json()
    assert body["data"], "expected faceted hits in Kitchen & Dining"
    # Every faceted hit is a real PDP the buyer can open, and stays in the facet.
    for result in body["data"]:
        pid = result["product"]["id"]
        detail = api_client.get(f"/products/{pid}")
        assert detail.status_code == 200
        assert detail.json()["data"]["category"] == "Kitchen & Dining"


# --------------------------------------------------------------------------- #
# the retrieval mode is stable across the journey (Decision-4 swap point)      #
# --------------------------------------------------------------------------- #
def test_retrieval_mode_stable_across_journey(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    # Whatever the query, the live discriminator is keyword today — the single value
    # Echo flips to semantic/hybrid later without any other contract change.
    for q in ("tide", "serving", "zzzznomatch"):
        meta = api_client.get(f"/search?q={q}").json()["meta"]
        assert meta["mode"] == SearchMode.keyword.value
