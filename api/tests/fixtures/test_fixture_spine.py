"""Proof that the 'one source -> three layers' spine is real, not vapor (US-QA-D06).

Three concerns, mirroring the golden-eval validator's two-layer style:

1. **Static** (no DB): the canonical catalog is internally consistent and the
   on-disk manifest matches the live handles (so the browser/agent layers that read
   JSON can't drift from the Python handles).
2. **Anti-drift / seed-resolve** (DB-backed, skips without a live Postgres): migrate
   + seed a throwaway DB and assert every canonical handle resolves to a real row.
3. **API-client spine** (DB-backed): the contract client can attempt a real
   ``/auth/login`` for every persona — green once Week-2's handler lands, ``xfail``
   while the route is a 501 contract stub. Proves the wiring + shape today.
"""

from __future__ import annotations

import json

import pytest

from tests.conftest import ContractClient, LoginNotReady, ResolvedHandles, SeededDb
from tests.fixtures.handles import (
    PAYMENT_TEST_MODE,
    PERSONAS,
    POLICY_HANDLES,
    PRODUCT_HANDLES,
    VARIANT_HANDLES,
)
from tests.fixtures.manifest import MANIFEST_PATH, build_manifest

# --------------------------------------------------------------------------- static


def test_catalog_handles_self_consistent() -> None:
    """Handles' dict keys equal their declared ``.handle`` (no copy/paste drift)."""
    for name, p in PERSONAS.items():
        assert p.handle == name
    for name, ph in PRODUCT_HANDLES.items():
        assert ph.handle == name
    for name, vh in VARIANT_HANDLES.items():
        assert vh.handle == name
    for name, poh in POLICY_HANDLES.items():
        assert poh.handle == name


def test_inventory_edge_states_present() -> None:
    """The variant handles span the stock edges the journeys need."""
    assert VARIANT_HANDLES["mug_in_stock"].in_stock
    assert VARIANT_HANDLES["mug_low_stock"].qty_on_hand in range(1, 6)  # low but >0
    assert not VARIANT_HANDLES["wallet_oos"].in_stock  # qty 0 -> out_of_stock path


def test_one_persona_per_role_covered() -> None:
    """All four contract roles are represented by at least one persona handle."""
    roles = {str(p.role) for p in PERSONAS.values()}
    assert {"buyer", "seller", "support", "admin"} <= roles


def test_policy_keys_match_golden_convention() -> None:
    """Policy ``key`` is '<kind>@<store|platform>' — the golden dataset's format."""
    assert POLICY_HANDLES["returns_platform"].key == "returns@platform"
    assert POLICY_HANDLES["returns_leather"].key == "returns@herrera-leather"


def test_payment_decline_switch_matches_contract() -> None:
    """The J-BUY-04 decline trigger matches contract-v0 §6 (ADR-0021)."""
    assert PAYMENT_TEST_MODE.decline_outcome == "failed"
    assert PAYMENT_TEST_MODE.declined_error_code == "payment_declined"
    assert PAYMENT_TEST_MODE.declined_http_status == 402


def test_manifest_on_disk_matches_live_handles() -> None:
    """The committed JSON manifest equals what the handles produce now.

    This is the anti-drift guard for the NON-Python layers: if someone edits
    ``handles.py`` without regenerating the manifest, the browser/agent layers would
    read stale data — so we fail until ``python -m tests.fixtures.manifest`` is rerun.
    """
    assert MANIFEST_PATH.is_file(), (
        f"manifest missing at {MANIFEST_PATH} — run `python -m tests.fixtures.manifest`"
    )
    on_disk = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert on_disk == build_manifest(), (
        "fixture-manifest.json is stale; regenerate with "
        "`python -m tests.fixtures.manifest`"
    )


# ----------------------------------------------------------------- seed-resolve (DB)


def test_seeded_db_brings_up_baseline(seeded_db: SeededDb) -> None:
    """The ``seeded_db`` fixture migrates + seeds a throwaway DB with real content."""
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from app.db.models import Policy, Product, User, Variant

    with Session(seeded_db.engine) as s:
        # Concrete floors from the seed (12 users, 10 products, 15 variants, 7 policies).
        assert (s.scalar(select(func.count()).select_from(User)) or 0) >= 12
        assert (s.scalar(select(func.count()).select_from(Product)) or 0) >= 10
        assert (s.scalar(select(func.count()).select_from(Variant)) or 0) >= 15
        assert (s.scalar(select(func.count()).select_from(Policy)) or 0) >= 7


def test_every_canonical_handle_resolves(handles: ResolvedHandles) -> None:
    """Anti-drift: every persona/product/variant/policy handle maps to a real row.

    The ``handles`` fixture raises during resolution if any handle is stale, so simply
    requesting it is the assertion; we additionally check the counts line up.
    """
    assert set(handles.user_ids) == set(PERSONAS)
    assert set(handles.product_ids) == set(PRODUCT_HANDLES)
    assert set(handles.variant_ids) == set(VARIANT_HANDLES)
    assert set(handles.policy_ids) == set(POLICY_HANDLES)
    # All ids are non-empty UUID strings.
    all_ids = (
        list(handles.user_ids.values())
        + list(handles.product_ids.values())
        + list(handles.variant_ids.values())
        + list(handles.policy_ids.values())
    )
    assert all(isinstance(i, str) and len(i) >= 32 for i in all_ids)


# ------------------------------------------------------------- API-client spine (DB)


@pytest.mark.parametrize("persona_handle", list(PERSONAS))
def test_api_client_mints_session_per_persona(
    api_client: ContractClient, seeded_db: SeededDb, persona_handle: str
) -> None:
    """The contract client attempts a real ``/auth/login`` for each persona.

    Today ``/auth/login`` is a 501 contract stub, so login raises ``LoginNotReady``;
    this is an EXPECTED xfail that flips to a real pass the moment Week-2's auth
    handler lands. It proves the fixture wiring + the contract login shape now.
    """
    persona = PERSONAS[persona_handle]
    try:
        token = api_client.login(persona)
    except LoginNotReady:
        pytest.xfail("/auth/login is a 501 contract stub until Week-2 handlers land")
    assert token and api_client.token == token
