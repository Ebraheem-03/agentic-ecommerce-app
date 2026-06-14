# Backend regression pack (US-QA-D13)

The **clean-seed full-surface regression** for the Week-2 backend. It proves the whole
API works in one coherent ordered pass against a single freshly-seeded throwaway DB, and
emits a human-readable report Atlas / the human read at the Day-14 W2 gate.

## What it is (and what it is NOT)

This is the **integration-pass** layer. It is deliberately *not* a copy of the
per-feature suites and does not re-assert their atoms. Those live where they belong:

| Surface | Per-feature suite (atoms / journeys) |
| --- | --- |
| auth | `tests/api/test_auth_handlers.py`, `tests/api/test_auth_e2e.py` |
| search / catalog | `tests/api/test_search.py`, `tests/api/test_search_e2e.py`, `tests/api/test_catalog.py` |
| cart / orders | `tests/api/test_cart_handlers.py`, `tests/api/test_orders_handlers.py`, `tests/api/test_checkout_e2e.py` |
| agent tools | `tests/agent/test_tool_e2e.py` (US-QA-D12 per-tool matrix) |
| eval | `tests/qa/test_golden_eval.py`, `test_retrieval_smoke.py`, `test_ragas_harness.py` |

The regression pack (`tests/regression/test_backend_regression.py`) adds the one thing no
single file above provides: **one ordered traversal of the whole surface on a clean
seed**, asserting the *cross-feature* invariants that only hold when the surfaces are
stitched in sequence:

```
auth (register/login/me) -> catalog (list/detail) -> search (keyword hit -> PDP)
  -> cart (add/update) -> order (checkout -> reserve -> intent -> capture -> status)
  -> agent tools (search + productDetails read, orderStatus, addToCart + draftOrder)
  -> the canonical {"error": {...}} envelope on a representative failure
```

Cross-feature invariants pinned here (and only here):

- the search hit, the catalog detail, and the agent `productDetails`/`search` tools all
  resolve to the **same seeded product** — REST and the agent see one catalog;
- the placed order's `total_minor` **==** the cart subtotal it was built from;
- reserve-at-checkout then capture move inventory by **exactly the ordered qty**;
- the agent `orderStatus` tool reports the **same order** as REST `GET /orders/{id}`;
- a representative failure carries the locked `{"error":{code,message,details}}` shape
  with a closed `ErrorCode` + HTTP status (never prose).

Error assertions pin the closed `ErrorCode` enum + HTTP status. Inventory deltas are read
live from the seeded DB (anti-drift) — no hardcoded counts. Fixtures (`seeded_db`,
`persona_client`, `handles`) are reused, never hand-seeded.

## Running it (one command, clean seed)

The DB must be up (compose `pgvector/pgvector:pg16`). From `api/`, with the venv active:

```bash
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/postgres \
  pytest tests/regression
```

or, by selector from anywhere in the suite:

```bash
DATABASE_URL=... pytest -k regression
```

Each test gets a pristine migrated + seeded throwaway DB (per-test CREATE/DROP via the
`migration_db` -> `seeded_db` fixtures), so the pass always runs from a clean seed.

## The report artifact

When the suite runs it writes a skimmable Markdown report:

- `regression-<date>.md` — the dated run (gitignored, regenerated each run)
- `regression-latest.md` — a stable pointer to the most recent run (gitignored)

The report header carries the **seed identity** (live seeded product count + label),
**timestamp**, and **counts** (surfaces green / total). The body is a per-surface table:
what was exercised, the key invariant asserted, and pass/fail. It is informational (the
artifact the gate reader skims), **not** itself a CI gate — the gate is the green suite.

Only this `README.md` is committed in `docs/qa/regression/`; the `regression-*.md` run
outputs are gitignored the same way the Day-10 `retrieval-smoke-*.json` artifacts are, so
the tree / CI do not churn on wall-clock stamps.
