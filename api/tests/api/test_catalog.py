"""Catalog endpoints — DB-backed contract behavior (US-E4-06).

Exercises the LIVE catalog read surface against the seeded throwaway DB via the
``seeded_db`` + ``api_client`` fixture spine (contract-v0 ``{data, meta}`` envelope,
cursor pagination, closed error codes). Covers:

  * GET /products            — happy list + envelope/meta shape
  * GET /products?cursor=…   — keyset cursor pagination walks the whole catalog once
  * GET /products?store_id=… / ?category= — filters narrow the result set
  * GET /products/{id|slug}  — detail by slug AND by id (variants/images/rating rollup)
  * GET /products/{id}       — 404 renders the canonical not_found envelope
  * inventory                — seeded low-stock + OOS variants surface in_stock correctly
  * GET /stores/{id|slug}    — store detail happy + 404

Pins on closed ``ErrorCode`` strings, never prose. Asserts via the seeded handles
(anti-drift) where a specific row matters.
"""

from __future__ import annotations

from app.schemas.envelope import ErrorCode
from tests.conftest import ContractClient, ResolvedHandles, SeededDb


# --------------------------------------------------------------------------- #
# Product list                                                                 #
# --------------------------------------------------------------------------- #
def test_list_products_happy_envelope(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    resp = api_client.get("/products")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"data", "meta"}
    assert isinstance(body["data"], list) and body["data"]
    # Seed catalog (10 active products) fits under the default limit of 24 -> one page.
    assert body["meta"]["limit"] == 24
    assert body["meta"]["next_cursor"] is None

    card = body["data"][0]
    # ProductSummary contract shape (snake_case, nested store summary).
    for key in ("id", "title", "slug", "status", "store", "from_price_minor", "currency"):
        assert key in card, f"missing {key} on product summary"
    assert card["status"] == "active"
    assert set(card["store"].keys()) >= {"id", "name", "slug", "status"}


def test_list_products_cursor_paginates_full_catalog(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    # Walk the catalog two-at-a-time via opaque cursors; assert no dupes/skips and that
    # the cursor terminates (next_cursor -> null) once every row is seen exactly once.
    seen: list[str] = []
    cursor: str | None = None
    for _ in range(50):  # generous guard against an infinite loop
        url = "/products?limit=2" + (f"&cursor={cursor}" if cursor else "")
        body = api_client.get(url).json()
        assert len(body["data"]) <= 2
        seen.extend(p["id"] for p in body["data"])
        cursor = body["meta"]["next_cursor"]
        if cursor is None:
            break
    assert cursor is None, "pagination did not terminate"
    assert len(seen) == len(set(seen)), "cursor pages overlapped"
    # Same set as a single big page.
    full = [p["id"] for p in api_client.get("/products?limit=100").json()["data"]]
    assert set(seen) == set(full)
    assert len(seen) == len(full)


def test_list_products_filter_by_store(
    seeded_db: SeededDb, api_client: ContractClient, handles: ResolvedHandles
) -> None:
    # The mug belongs to solveig-ceramics; filtering by that store returns only its rows.
    mug = api_client.get(f"/products/{handles.product_ids['mug']}").json()["data"]
    store_id = mug["store"]["id"]
    body = api_client.get(f"/products?store_id={store_id}").json()
    assert body["data"]
    assert all(p["store"]["id"] == store_id for p in body["data"])
    # Fewer than the full catalog (the store doesn't own every product).
    full = api_client.get("/products?limit=100").json()["data"]
    assert len(body["data"]) < len(full)


def test_list_products_filter_by_category(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    body = api_client.get("/products?category=Accessories").json()
    assert body["data"]
    assert all(p["category"] == "Accessories" for p in body["data"])


def test_list_products_bad_cursor_is_validation_error(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    resp = api_client.get("/products?cursor=not-a-real-cursor")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == ErrorCode.validation_error.value


# --------------------------------------------------------------------------- #
# Product detail                                                               #
# --------------------------------------------------------------------------- #
def test_get_product_detail_by_slug(
    seeded_db: SeededDb, api_client: ContractClient, handles: ResolvedHandles
) -> None:
    resp = api_client.get("/products/tide-pour-over-mug")
    assert resp.status_code == 200
    detail = resp.json()["data"]
    assert resp.json()["meta"] is None
    assert detail["id"] == handles.product_ids["mug"]
    assert detail["slug"] == "tide-pour-over-mug"
    # ProductDetail adds variants/images/description over the summary.
    assert isinstance(detail["variants"], list) and detail["variants"]
    assert isinstance(detail["images"], list)
    assert "description" in detail and "attributes" in detail
    # rating rollup columns are surfaced (mug has reviews seeded).
    assert detail["rating_count"] >= 0


def test_get_product_detail_by_id_matches_slug(
    seeded_db: SeededDb, api_client: ContractClient, handles: ResolvedHandles
) -> None:
    pid = handles.product_ids["mug"]
    by_id = api_client.get(f"/products/{pid}").json()["data"]
    by_slug = api_client.get("/products/tide-pour-over-mug").json()["data"]
    assert by_id == by_slug


def test_get_product_missing_is_not_found_envelope(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    resp = api_client.get("/products/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    body = resp.json()
    assert body == {
        "error": {
            "code": ErrorCode.not_found.value,
            "message": body["error"]["message"],
            "details": None,
        }
    }
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]


# --------------------------------------------------------------------------- #
# Inventory surfacing (the point of the story)                                 #
# --------------------------------------------------------------------------- #
def test_inventory_in_stock_low_stock_and_oos_surface(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    # Mug has an in-stock variant (SOL-MUG-SAGE, qty 24) and a low-stock one
    # (SOL-MUG-ASH, qty 3 + restock_eta 10): both are still in_stock=True.
    mug = api_client.get("/products/tide-pour-over-mug").json()["data"]
    by_sku = {v["sku"]: v for v in mug["variants"]}
    assert by_sku["SOL-MUG-SAGE"]["in_stock"] is True
    low = by_sku["SOL-MUG-ASH"]
    assert low["in_stock"] is True
    assert low["restock_eta_days"] == 10  # low-stock still surfaces a restock eta

    # Wallet has an OOS variant (HER-WAL-ESP, qty 0) -> in_stock=False + restock eta.
    wallet = api_client.get("/products/carryall-card-wallet").json()["data"]
    wal_by_sku = {v["sku"]: v for v in wallet["variants"]}
    oos = wal_by_sku["HER-WAL-ESP"]
    assert oos["in_stock"] is False
    assert oos["restock_eta_days"] == 21
    assert wal_by_sku["HER-WAL-TAN"]["in_stock"] is True  # qty 18


# --------------------------------------------------------------------------- #
# Store detail                                                                 #
# --------------------------------------------------------------------------- #
def test_get_store_detail_by_slug(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    resp = api_client.get("/stores/solveig-ceramics")
    assert resp.status_code == 200
    store = resp.json()["data"]
    assert store["slug"] == "solveig-ceramics"
    for key in ("id", "name", "slug", "status", "created_at"):
        assert key in store
    # by id matches by slug
    by_id = api_client.get(f"/stores/{store['id']}").json()["data"]
    assert by_id == store


def test_get_store_missing_is_not_found_envelope(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    resp = api_client.get("/stores/no-such-store")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == ErrorCode.not_found.value
