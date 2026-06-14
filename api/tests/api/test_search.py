"""Search endpoint — DB-backed keyword retrieval + contract shape (US-E4-07).

Exercises GET /search over the seeded throwaway catalog via the ``seeded_db`` +
``api_client`` spine (contract-v0 ``{data, meta}`` envelope, closed error codes). Keyword
retrieval is the LIVE path (Postgres full-text, ``ts_rank``); the response surfaces the
retrieval ``mode`` discriminator (``meta.mode``) + a per-result ``score`` so semantic/
pgvector retrieval drops in behind the same shape later (Decision-4). Covers:

  * relevance        — a distinctive seed term ranks the right product first, with a score
  * mode/score shape — ``meta.mode == 'keyword'`` (the live discriminator), score present
  * category filter  — narrows results to one category
  * no-match         — empty ``data`` (a 200, NOT a 404)
  * validation       — empty / over-long ``q`` -> 422 canonical envelope (closed code)

Pins on closed ``ErrorCode`` strings + seeded handles (anti-drift), never prose.
"""

from __future__ import annotations

from app.schemas.envelope import ErrorCode
from app.schemas.search import SearchMode
from tests.conftest import ContractClient, ResolvedHandles, SeededDb


# --------------------------------------------------------------------------- #
# Relevance — the point of the story                                           #
# --------------------------------------------------------------------------- #
def test_search_ranks_relevant_product_first(
    seeded_db: SeededDb, api_client: ContractClient, handles: ResolvedHandles
) -> None:
    # "tide" appears in the mug's title ("Tide Pour-Over Mug") and description — a
    # distinctive seed term that should rank the mug first via title-weighted ts_rank.
    resp = api_client.get("/search?q=tide")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"data", "meta"}
    assert body["data"], "expected at least one match for 'tide'"
    top = body["data"][0]
    assert top["product"]["id"] == handles.product_ids["mug"]
    assert top["product"]["slug"] == "tide-pour-over-mug"


def test_search_result_carries_mode_and_score(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    body = api_client.get("/search?q=mug").json()
    # Mode discriminator is the LIVE keyword path today (Decision-4 swap point).
    assert body["meta"]["mode"] == SearchMode.keyword.value
    assert body["data"]
    first = body["data"][0]
    # Per-result shape: a ProductSummary under `product` + a numeric relevance `score`.
    assert "product" in first and "score" in first
    assert isinstance(first["score"], (int, float))
    assert first["score"] > 0.0  # a real match has a positive ts_rank
    for key in ("id", "title", "slug", "status", "store"):
        assert key in first["product"]


def test_search_results_ordered_by_descending_score(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    # "serving" matches >1 product (Ebb Serving Bowl + Nara Serving Spoons); scores must
    # be non-increasing. (websearch_to_tsquery ANDs space-separated terms, so we use a
    # single shared term to get multiple matches.)
    body = api_client.get("/search?q=serving&limit=100").json()
    scores = [r["score"] for r in body["data"]]
    assert len(scores) >= 2, "expected multiple matches for 'serving'"
    assert scores == sorted(scores, reverse=True)


# --------------------------------------------------------------------------- #
# Filters                                                                      #
# --------------------------------------------------------------------------- #
def test_search_category_filter_narrows_results(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    # "serving OR wallet" spans categories: Serving Bowl/Spoons (Kitchen & Dining) +
    # Card Wallet (Accessories). websearch_to_tsquery understands the OR operator.
    query = "serving+OR+wallet"
    unfiltered = api_client.get(f"/search?q={query}&limit=100").json()
    assert unfiltered["data"]
    categories = {r["product"]["category"] for r in unfiltered["data"]}
    assert len(categories) >= 2, "query should span >1 category before filtering"

    # Filtering to one category narrows the set to only that category's rows.
    body = api_client.get(
        f"/search?q={query}&category=Kitchen+%26+Dining&limit=100"
    ).json()
    assert body["data"]
    assert all(r["product"]["category"] == "Kitchen & Dining" for r in body["data"])
    assert len(body["data"]) < len(unfiltered["data"])


# --------------------------------------------------------------------------- #
# No match -> empty data (NOT a 404)                                           #
# --------------------------------------------------------------------------- #
def test_search_no_match_returns_empty_data_not_404(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    resp = api_client.get("/search?q=zzzznonexistentterm")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["meta"]["mode"] == SearchMode.keyword.value
    assert body["meta"]["total"] == 0
    assert body["meta"]["next_cursor"] is None


# --------------------------------------------------------------------------- #
# Validation -> canonical envelope, closed code                               #
# --------------------------------------------------------------------------- #
def test_search_empty_query_is_validation_error(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    resp = api_client.get("/search?q=")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == ErrorCode.validation_error.value


def test_search_missing_query_is_validation_error(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    resp = api_client.get("/search")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == ErrorCode.validation_error.value


def test_search_over_long_query_is_validation_error(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    resp = api_client.get("/search?q=" + "a" * 201)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == ErrorCode.validation_error.value


def test_search_limit_is_capped(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    # limit > 100 violates the contract guard -> validation error (closed code).
    resp = api_client.get("/search?q=mug&limit=101")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == ErrorCode.validation_error.value
