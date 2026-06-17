"""API latency budgets — in-process p50/p95 for hot endpoints (US-E7-07, QA slice).

WHAT THIS IS
============
A lightweight, DETERMINISTIC latency check over the ASGI app (the ``api_client`` test
client, no network) for a few HOT read/write endpoints. It times N repetitions per
endpoint, computes p50/p95 (``statistics.quantiles``), and asserts each p95 against a
stated IN-PROCESS budget. "Budgets met or defects created": a breach FAILS the test with
the measured numbers so Atlas files a defect — it does not silently pass.

WHAT THIS IS NOT
================
NOT a production SLO. These are in-process numbers over the TestClient + a seeded
throwaway DB: no network hop, no TLS, no real provider. They guard against gross
in-process regressions (an N+1, an accidental full-table scan) — the budget is generous
(p95 < 300ms in-process) precisely because the absolute floor is environment-bound. The
measured p50/p95 are printed so a human can read the actual shape, not just pass/fail.

WARMUP
======
The first call per endpoint pays one-time costs (lazy imports, connection-pool fill,
SQLAlchemy compilation) that aren't representative of steady-state latency, so a warmup
request per endpoint is discarded before timing.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable

import pytest

from tests.conftest import ContractClient, ResolvedHandles, SeededDb

# In-process p95 budget (ms). Generous on purpose — see module docstring.
_P95_BUDGET_MS = 300.0
_REPS = 25


def _percentiles(samples_ms: list[float]) -> tuple[float, float]:
    """(p50, p95) in ms. Uses inclusive quantiles; falls back for tiny n."""
    p50 = statistics.median(samples_ms)
    # quantiles(n=100) needs >=2 points; _REPS is 25 so this is always satisfied.
    p95 = statistics.quantiles(samples_ms, n=100, method="inclusive")[94]
    return p50, p95


def _time_endpoint(call: Callable[[], object], *, reps: int = _REPS) -> list[float]:
    """Warm once (discarded), then time ``reps`` calls; return per-call ms."""
    call()  # warmup — discard one-time costs
    out: list[float] = []
    for _ in range(reps):
        start = time.perf_counter()
        call()
        out.append((time.perf_counter() - start) * 1000.0)
    return out


def _assert_budget(name: str, samples_ms: list[float]) -> None:
    p50, p95 = _percentiles(samples_ms)
    # Surfaced even on pass (pytest -s / on failure) so the actual shape is visible.
    print(
        f"\n[latency] {name}: p50={p50:.1f}ms p95={p95:.1f}ms "
        f"(n={len(samples_ms)}, budget p95<{_P95_BUDGET_MS:.0f}ms)"
    )
    assert p95 < _P95_BUDGET_MS, (
        f"LATENCY DEFECT: {name} p95={p95:.1f}ms exceeds the "
        f"{_P95_BUDGET_MS:.0f}ms in-process budget (p50={p50:.1f}ms). File a defect."
    )


def test_latency_get_products(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    """GET /products (browse) p95 within the in-process budget."""
    samples = _time_endpoint(lambda: api_client.get("/products?limit=24"))
    _assert_budget("GET /products", samples)


def test_latency_get_search(
    seeded_db: SeededDb, api_client: ContractClient
) -> None:
    """GET /search (keyword) p95 within the in-process budget."""
    samples = _time_endpoint(lambda: api_client.get("/search?q=mug&limit=24"))
    _assert_budget("GET /search", samples)


@pytest.mark.parametrize("persona_client", ["buyer_primary"], indirect=True)
def test_latency_post_cart_items(
    seeded_db: SeededDb, persona_client: ContractClient, handles: ResolvedHandles
) -> None:
    """POST /cart/items (idempotent upsert) p95 within the in-process budget.

    The same in-stock variant is re-added each rep — an idempotent qty upsert, so the cart
    stays one line and the write path (validate -> stock check -> upsert) is exercised
    repeatedly without unbounded growth skewing the tail.
    """
    variant_id = handles.variant_ids["mug_in_stock"]
    samples = _time_endpoint(
        lambda: persona_client.post(
            "/cart/items", json={"variant_id": variant_id, "qty": 1}
        )
    )
    _assert_budget("POST /cart/items", samples)
