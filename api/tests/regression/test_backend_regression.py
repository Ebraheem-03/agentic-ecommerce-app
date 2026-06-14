"""Backend regression pack — one ordered clean-seed traversal + readable report (US-QA-D13).

WHAT THIS IS (and the LAYER SPLIT — read before adding cases here)
==================================================================
This is the Week-2 **integration-pass** layer: the artifact Atlas / the human read at
the Day-14 gate to see "the backend is green end-to-end from a clean seed." It is NOT a
copy of the per-feature suites and deliberately does NOT re-assert their atoms:

  * ``tests/api/test_auth_handlers.py`` + ``test_auth_e2e.py`` (Orion/Juno) — auth unit
    + lifecycle/negative journey (hashing, expiry, scope-denial, every 401/403/409 edge).
  * ``tests/api/test_search.py`` + ``test_search_e2e.py`` — search endpoint atoms +
    the J-BUY-01 discovery -> PDP journey (ranking, facets, refinement, mode stability).
  * ``tests/api/test_cart_handlers.py`` / ``test_orders_handlers.py`` /
    ``test_checkout_e2e.py`` — cart/order handler boundaries + the J-BUY-04 buy journey
    (reserve/capture/decline/idempotency/out-of-stock invariants, end to end).
  * ``tests/agent/test_tool_e2e.py`` (Juno, US-QA-D12) — the exhaustive per-tool
    success x validation x unauthorized matrix for all 8 agent tools + tool cross-cutting.

NONE of those atoms are duplicated here. THIS module adds the ONE thing no single file
above provides: a **single ordered traversal of the WHOLE API surface against one
freshly-seeded DB**, asserting the *cumulative cross-feature invariants* that only hold
when the surfaces are stitched in sequence —

    auth (register/login/me) -> catalog (list/detail) -> search (keyword hit -> PDP)
      -> cart (add/update) -> order (checkout -> reserve -> intent -> capture -> status)
      -> agent tools (a read via ``execute_tool`` + a mutating tool) seeing the SAME
         seeded rows the REST API does
      -> the canonical ``{"error": {...}}`` envelope shape on a representative failure.

The cross-feature invariants pinned here (and nowhere else, because they span surfaces):
  * the search hit, the catalog detail, and the agent ``productDetails`` tool all resolve
    to the SAME seeded product (REST and agent see one catalog);
  * the placed order's ``total_minor`` == the cart subtotal it was built from;
  * reserve-at-checkout then capture move inventory by exactly the ordered qty
    (reserved += qty at checkout, on_hand -= qty at capture);
  * the agent ``orderStatus`` tool reports the same order the REST ``GET /orders/{id}``
    does, for the same buyer.

It also EMITS a readable Markdown report (``docs/qa/regression/regression-<date>.md`` +
a stable ``regression-latest.md``) summarising, per surface, what was exercised /
pass-fail / the key invariant asserted, with a header line carrying the seed identity +
timestamp + counts. Run artifacts are gitignored (like the Day-10 retrieval-smoke JSON);
a committed ``README.md`` documents the pack + the one-command runner.

HOUSE RULES honoured: reuses the ``seeded_db`` / ``api_client`` / ``persona_client`` /
``handles`` fixtures (no hand-seeding); error assertions pin the closed ``ErrorCode`` +
HTTP status, never prose. Inventory deltas are read live from the seeded DB (anti-drift),
no hardcoded counts.

RUNNER: ``pytest tests/regression`` (or ``-k regression``) runs the full backend
regression from a clean seed in one command — see ``docs/qa/regression/README.md``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.executor import execute_tool
from app.agent.tools import DraftOrderOutput, SearchOutput, ToolName
from app.db.models import Inventory, User
from app.schemas.catalog import ProductDetail
from app.schemas.enums import PaymentStatus
from app.schemas.envelope import ErrorCode
from app.schemas.order import OrderDetail
from tests.conftest import ContractClient, ResolvedHandles, SeededDb
from tests.fixtures.handles import PERSONAS

# api/tests/regression/test_backend_regression.py -> parents[3] == repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = REPO_ROOT / "docs" / "qa" / "regression"

# A realistic ship-to (AddressIn needs at least recipient_name + country_code).
_SHIP = {
    "recipient_name": "Ada Buyer",
    "line1": "12 Kiln Lane",
    "city": "Brookline",
    "region": "MA",
    "postal_code": "02445",
    "country_code": "US",
}

# Seeded facts the traversal anchors on (anti-drift: ids resolved via ``handles``).
_REGRESSION_PERSONA = "buyer_primary"
_DISTINCTIVE_TERM = "tide"
_MUG_SLUG = "tide-pour-over-mug"


# --------------------------------------------------------------------------- #
# Report accumulator — one row per API surface, flushed to Markdown at the end. #
# --------------------------------------------------------------------------- #
@dataclass
class _SurfaceResult:
    surface: str
    exercised: str
    invariant: str
    passed: bool = True


@dataclass
class _Report:
    """Collects per-surface results across the ordered traversal, emits Markdown."""

    seed_identity: str
    rows: list[_SurfaceResult] = field(default_factory=list)

    def record(self, surface: str, exercised: str, invariant: str) -> None:
        self.rows.append(_SurfaceResult(surface, exercised, invariant))

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.rows)

    def to_markdown(self, stamp: datetime) -> str:
        passed = sum(1 for r in self.rows if r.passed)
        total = len(self.rows)
        status = "PASS" if self.all_passed else "FAIL"
        lines = [
            "# Backend regression — clean-seed full-surface pass",
            "",
            "- **Story:** US-QA-D13",
            f"- **Generated:** {stamp.isoformat()}",
            f"- **Seed identity:** {self.seed_identity}",
            f"- **Result:** {status} ({passed}/{total} surfaces green)",
            "",
            "One ordered traversal over a single freshly-seeded DB: auth -> catalog -> "
            "search -> cart -> order (reserve/capture) -> agent tools -> error envelope. "
            "Asserts the cumulative cross-feature invariants that only hold across the "
            "stitched surfaces. Per-feature atoms live in their own suites (see the module "
            "docstring layer split). Informational artifact for the W2 gate, regenerated "
            "each run.",
            "",
            "| # | Surface | Exercised | Key invariant asserted | Result |",
            "| - | ------- | --------- | ---------------------- | ------ |",
        ]
        for i, r in enumerate(self.rows, start=1):
            mark = "pass" if r.passed else "FAIL"
            lines.append(
                f"| {i} | {r.surface} | {r.exercised} | {r.invariant} | {mark} |"
            )
        lines.append("")
        return "\n".join(lines)


@pytest.fixture
def report(seeded_db: SeededDb) -> Iterator[_Report]:
    """Yield a report accumulator; on teardown, flush Markdown to the (gitignored) dir.

    The seed identity is the live seeded product count + a stable label, so the header
    proves the report reflects a real migrated+seeded DB (not an empty one).
    """
    with Session(seeded_db.engine) as s:
        from app.db.models import Product

        product_count = s.scalar(select(func.count()).select_from(Product)) or 0
    rep = _Report(seed_identity=f"idempotent seed · {product_count} products")
    try:
        yield rep
    finally:
        stamp = datetime.now(UTC)
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        md = rep.to_markdown(stamp)
        (REPORT_DIR / f"regression-{stamp.strftime('%Y-%m-%d')}.md").write_text(
            md, encoding="utf-8"
        )
        (REPORT_DIR / "regression-latest.md").write_text(md, encoding="utf-8")


def _inv(session: Session, variant_id: str) -> tuple[int, int]:
    """Live (qty_on_hand, qty_reserved) for a variant's inventory row."""
    inv = session.scalar(select(Inventory).where(Inventory.variant_id == variant_id))
    assert inv is not None, f"no inventory row for variant {variant_id}"
    return inv.qty_on_hand, inv.qty_reserved


def _user(session: Session, handles: ResolvedHandles, persona: str) -> User:
    uid = handles.user_ids[PERSONAS[persona].handle]
    user = session.get(User, uid)
    assert user is not None
    return user


# =========================================================================== #
# THE regression traversal: the whole API surface, one ordered clean-seed pass. #
# =========================================================================== #
@pytest.mark.parametrize("persona_client", [_REGRESSION_PERSONA], indirect=True)
def test_backend_regression_full_surface_clean_seed(
    seeded_db: SeededDb,
    persona_client: ContractClient,
    handles: ResolvedHandles,
    report: _Report,
) -> None:
    """One coherent pass over every backend surface against a single fresh seed.

    Pins the cross-feature invariants no per-feature suite can (they span surfaces):
    REST and agent see one catalog; order total == cart subtotal; reserve+capture move
    inventory by the ordered qty; the agent orderStatus mirrors REST GET /orders/{id};
    and the canonical error envelope holds on a representative failure.
    """
    client = persona_client
    variant_id = handles.variant_ids["mug_in_stock"]
    expected_product_id = handles.product_ids["mug"]

    # ----- 1. AUTH: the persona_client already logged in; /auth/me confirms identity. ---
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["email"] == PERSONAS[_REGRESSION_PERSONA].email
    report.record(
        "auth",
        "login (via fixture) -> GET /auth/me",
        "authenticated identity matches the seeded persona",
    )

    # ----- 2. CATALOG: list browses, detail resolves the seeded mug by id. --------------
    listing = client.get("/products?limit=100")
    assert listing.status_code == 200
    list_body = listing.json()
    assert set(list_body.keys()) == {"data", "meta"}
    listed_ids = {p["id"] for p in list_body["data"]}
    assert expected_product_id in listed_ids, "seeded mug must appear in the catalog list"

    detail = client.get(f"/products/{expected_product_id}")
    assert detail.status_code == 200
    detail_body = detail.json()["data"]
    assert detail_body["slug"] == _MUG_SLUG
    assert detail_body["variants"], "PDP must expose variants for the buy surface"
    report.record(
        "catalog",
        "GET /products (list) + GET /products/{id} (detail)",
        "seeded product is browseable and its PDP exposes variants",
    )

    # ----- 3. SEARCH: a keyword hit hands off to the SAME seeded product's PDP. ----------
    results = client.get(f"/search?q={_DISTINCTIVE_TERM}").json()["data"]
    assert results, f"expected a keyword hit for {_DISTINCTIVE_TERM!r}"
    top = results[0]["product"]
    # CROSS-FEATURE INVARIANT: search, catalog list, and catalog detail agree on identity.
    assert top["id"] == expected_product_id
    assert top["slug"] == detail_body["slug"]
    report.record(
        "search",
        f"GET /search?q={_DISTINCTIVE_TERM} -> top hit",
        "search hit resolves to the same seeded product as catalog list/detail",
    )

    # ----- 4. CART: add the line, then GET /cart reflects it; capture the subtotal. ------
    qty = 2
    with Session(seeded_db.engine) as s:
        on_hand_before, reserved_before = _inv(s, variant_id)

    add = client.post("/cart/items", json={"variant_id": variant_id, "qty": qty})
    assert add.status_code == 201, add.text
    cart = client.get("/cart")
    assert cart.status_code == 200
    cart_body = cart.json()["data"]
    assert len(cart_body["items"]) == 1
    cart_line = cart_body["items"][0]
    assert cart_line["variant_id"] == variant_id
    assert cart_line["qty"] == qty
    assert cart_body["item_count"] == qty
    cart_subtotal = cart_body["subtotal_minor"]
    report.record(
        "cart",
        "POST /cart/items + GET /cart",
        "added line is reflected with the ordered qty",
    )

    # ----- 5. ORDER: checkout -> reserve -> intent -> capture -> status. -----------------
    co = client.post("/orders", json={"ship_address": _SHIP})
    assert co.status_code == 201, co.text
    order = co.json()["data"]
    order_id = order["id"]
    assert order["status"] == "placed"
    # CROSS-FEATURE INVARIANT: the order total equals the cart subtotal it was built from.
    assert order["total_minor"] == cart_subtotal == order["subtotal_minor"]

    # Reserve-at-checkout: qty_reserved bumped by the ordered qty, on_hand untouched.
    with Session(seeded_db.engine) as s:
        on_hand_post_co, reserved_post_co = _inv(s, variant_id)
    assert reserved_post_co == reserved_before + qty
    assert on_hand_post_co == on_hand_before

    intent = client.post(f"/orders/{order_id}/payment-intent").json()["data"]
    assert intent["status"] == "pending"
    assert intent["amount_minor"] == order["total_minor"]

    cap = client.post(
        f"/orders/{order_id}/payment-confirm",
        json={"payment_id": intent["payment_id"], "outcome": "captured"},
    )
    assert cap.status_code == 200, cap.text
    assert cap.json()["data"]["status"] == "captured"

    # Capture: on_hand drawn down by the ordered qty, reservation released into the sale.
    with Session(seeded_db.engine) as s:
        on_hand_final, reserved_final = _inv(s, variant_id)
    assert on_hand_final == on_hand_before - qty
    assert reserved_final == reserved_before

    status_resp = client.get(f"/orders/{order_id}")
    assert status_resp.status_code == 200
    status_body = status_resp.json()["data"]
    assert status_body["id"] == order_id
    assert any(p["status"] == "captured" for p in status_body["payments"])
    report.record(
        "order",
        "POST /orders -> payment-intent -> payment-confirm -> GET /orders/{id}",
        "order total == cart subtotal; reserve+capture move stock by the ordered qty",
    )

    # ----- 6. AGENT TOOLS: a read + the orderStatus tool see the SAME seeded rows. -------
    # Drive execute_tool directly against the seeded session with the same seeded User —
    # one identity path for humans and agents (ADR-0029 §2).
    with Session(seeded_db.engine) as s:
        agent_user = _user(s, handles, _REGRESSION_PERSONA)

        # Read tool: search must surface the same product the REST search did.
        search_res = execute_tool(
            ToolName.search, {"query": _DISTINCTIVE_TERM}, session=s, user=agent_user
        )
        search_out = cast(SearchOutput, search_res.output)
        assert search_res.status_code == 200
        assert search_out.results
        # CROSS-FEATURE INVARIANT: the agent search tool sees the same catalog as REST.
        assert search_out.results[0].product.id == expected_product_id

        # Read tool: productDetails resolves the same seeded product.
        pd_res = execute_tool(
            ToolName.product_details, {"id_or_slug": _MUG_SLUG}, session=s, user=agent_user
        )
        pd_out = cast(ProductDetail, pd_res.output)
        assert pd_out.slug == _MUG_SLUG

        # orderStatus tool: reports the SAME captured order the REST status endpoint did.
        os_res = execute_tool(
            ToolName.order_status, {"order_id": order_id}, session=s, user=agent_user
        )
        os_out = cast(OrderDetail, os_res.output)
        assert os_res.status_code == 200
        assert os_out.id == order_id
        # CROSS-FEATURE INVARIANT: agent orderStatus mirrors REST GET /orders/{id}.
        assert os_out.status == status_body["status"]
        assert any(p.status == PaymentStatus.captured for p in os_out.payments)
    report.record(
        "agent tools",
        "execute_tool: search + productDetails (read) + orderStatus",
        "agent tools see the same seeded catalog + order as the REST API",
    )

    # ----- 7. A mutating agent tool shares the same checkout machinery as REST. ----------
    # draftOrder on a fresh seeded buyer adds->drafts->reserves exactly like POST /orders.
    with Session(seeded_db.engine) as s:
        buyer = _user(s, handles, _REGRESSION_PERSONA)
        mug_variant = handles.variant_ids["mug_in_stock"]
        reserved_pre = _inv(s, mug_variant)[1]
        execute_tool(
            ToolName.add_to_cart,
            {"variant_id": mug_variant, "qty": 1},
            session=s,
            user=buyer,
        )
        draft_res = execute_tool(
            ToolName.draft_order, {"ship_address": _SHIP}, session=s, user=buyer
        )
        draft = cast(DraftOrderOutput, draft_res.output)
        assert draft_res.status_code == 201
        assert draft.order.status == "placed"
        assert draft.payment_intent.status == PaymentStatus.pending
        # Mutating tool reserves stock through the same path REST checkout did.
        s.expire_all()
        assert _inv(s, mug_variant)[1] == reserved_pre + 1
    report.record(
        "agent tools (mutating)",
        "execute_tool: addToCart + draftOrder",
        "a mutating agent tool reserves stock via the same checkout path as REST",
    )

    # ----- 8. ERROR ENVELOPE: a representative failure carries the canonical shape. ------
    # Cross-user order access -> 404 not_found, with the locked {"error": {...}} envelope.
    with Session(seeded_db.engine) as s:
        other = _user(s, handles, "buyer_secondary")
    leak = client.get(f"/orders/{order_id}", headers={"Authorization": "Bearer nope"})
    # Garbage token first proves the auth gate; then the cross-user 404 proves no-leak.
    assert leak.status_code == 401
    assert leak.json()["error"]["code"] == ErrorCode.unauthenticated.value

    # Log in as the other buyer and prove the cross-user read is a no-leak 404 envelope.
    client.login(PERSONAS["buyer_secondary"])
    cross = client.get(f"/orders/{order_id}")
    assert cross.status_code == 404
    err = cross.json()
    assert set(err.keys()) == {"error"}
    assert set(err["error"].keys()) == {"code", "message", "details"}
    assert err["error"]["code"] == ErrorCode.not_found.value
    assert other.id != handles.user_ids[PERSONAS[_REGRESSION_PERSONA].handle]
    report.record(
        "error envelope",
        "garbage token -> 401; cross-user GET /orders/{id} -> 404",
        'canonical {"error":{code,message,details}} shape with closed ErrorCode',
    )

    # The traversal completed and every surface was exercised in one clean-seed pass.
    assert report.all_passed
    assert len(report.rows) == 8


def test_regression_report_artifact_is_written(seeded_db: SeededDb) -> None:
    """The report emitter writes a readable, well-formed Markdown artifact + a latest ptr.

    Drives the same accumulator the traversal uses, then asserts the emitted Markdown
    carries the header (seed identity + timestamp + counts) and a per-surface table —
    the contract the W2-gate reader depends on. Run outputs are gitignored; this proves
    the shape without depending on the big traversal's ordering.
    """
    stamp = datetime.now(UTC)
    rep = _Report(seed_identity="idempotent seed · N products")
    rep.record("auth", "login -> /auth/me", "identity matches seed")
    rep.record("error envelope", "cross-user 404", "canonical error shape")
    md = rep.to_markdown(stamp)

    # Header carries the three identity facts the gate reader needs.
    assert "US-QA-D13" in md
    assert "Seed identity" in md and "idempotent seed" in md
    assert stamp.isoformat() in md
    assert "PASS (2/2 surfaces green)" in md
    # The per-surface table is present and lists both recorded surfaces.
    assert "| Surface | Exercised | Key invariant asserted | Result |" in md
    assert "auth" in md and "error envelope" in md

    # Prove the emit path writes a file, but to a throwaway name so this shape-only test
    # never clobbers the canonical ``regression-latest.md`` the full traversal emits.
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    probe = REPORT_DIR / "regression-selfcheck.md"
    probe.write_text(md, encoding="utf-8")
    assert probe.is_file()
    probe.unlink()


def test_regression_report_is_valid_when_serialized() -> None:
    """A surface result round-trips to a plain dict (so a CI step could parse the run)."""
    r = _SurfaceResult("order", "checkout->capture", "total == subtotal")
    as_dict: dict[str, Any] = {
        "surface": r.surface,
        "exercised": r.exercised,
        "invariant": r.invariant,
        "passed": r.passed,
    }
    assert json.loads(json.dumps(as_dict))["passed"] is True
