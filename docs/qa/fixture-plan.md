# E2E Fixture Plan v0 — US-QA-D06

> Status: **Spine executable (2026-06-14).** Owner: Juno (QA & Integration).
> Acceptance criterion: **one source drives API, browser, and agent tests.**
> This doc is the design; the scaffolding that makes it real lives in
> `api/tests/fixtures/` + `api/tests/conftest.py` + `e2e/tests/_fixtures.ts`.

This plan makes "one canonical fixture definition → three test layers" concrete, so
the FastAPI/httpx API tests, the Playwright browser E2E specs, and the agent /
golden-eval checks all pin to the **same** seeded rows and never silently drift.

## 0. The one source, at a glance

```
app/db/seed/data.py                 <- THE content (12 users, 5 stores, 10 products,
   │                                    15 variants, inventory, 12 reviews, 7 policies)
   │  (idempotent upserts, run.py)
   ▼
api/tests/fixtures/handles.py       <- THE canonical handles: stable ids derived FROM
   │                                    the seed (never duplicated). buyer_primary,
   │                                    mug_low_stock, wallet_oos, returns_platform, …
   ├──────────────► api/tests/conftest.py
   │                   seeded_db  (migrate→seed throwaway DB; reuses Sable's migration_db)
   │                   handles    (every handle resolved to a real seeded UUID — anti-drift)
   │                   api_client / persona_client  (contract-v0 httpx client + login)
   │                        └─► API LAYER (httpx, Bearer token, {data,meta} envelope)
   │
   └──────────────► api/tests/fixtures/manifest.py
                       fixture-manifest.json  (generated, committed)
                          ├─► BROWSER LAYER  (e2e/tests/_fixtures.ts imports the JSON)
                          └─► AGENT LAYER    (golden-v0 source_docs resolve to same rows)
```

One rule underpins everything: **handles reference the seed; they never copy it.**
`handles.py` imports `app.db.seed.data` and pulls live emails/slugs/skus/prices/stock
out of it. A handle that names a row the seed no longer has fails the spine test
(`api/tests/fixtures/test_fixture_spine.py`) — the same anti-drift guarantee the
golden-eval validator already gives the agent layer.

---

## 1. Canonical fixture catalog

Source of truth: `api/tests/fixtures/handles.py`. Stable handle → natural key the
contract/seed resolves it by → the salient fact a test pins to.

### 1.1 Personas / accounts

All resolved by **email** against the seed `USERS`. Auth path is contract-v0:
`POST /auth/login {email, password}` → `200 {data: SessionOut{token,…}, meta:null}`;
the `token` is sent as `Authorization: Bearer <token>` on every authed call; logout
deletes the session row (instant revocation). The seed provisions **identities only**
(no passwords yet), so the fixture contract pins a single deterministic test password
(`CHANGE_ME_test_pw`) per persona; Week-2's auth-backed seeding must write exactly
those credentials. Until then, login is `xfail`-guarded (see §3).

| Handle | Email | Role | Used for |
|---|---|---|---|
| `buyer_primary` | ada@buyers.hearth.test | buyer | search→cart→checkout→order→status; returns |
| `buyer_secondary` | ben@buyers.hearth.test | buyer | isolation (foreign-order lookup, second cart) |
| `seller_ceramics` | mara@makers.hearth.test | seller | owns Sólveig Ceramics (the `mug`) |
| `seller_leather` | tomas@makers.hearth.test | seller | owns Herrera Leather (the `card_wallet`, `belt`) |
| `support` | support@hearth.test | support | order/policy lookup, return decide, HITL |
| `admin` | admin@hearth.test | admin | policy/guardrail review + edit |

### 1.2 Products (resolved by slug)

| Handle | Slug | Store | Why pinned |
|---|---|---|---|
| `mug` | tide-pour-over-mug | solveig-ceramics | the canonical search / compare / recommend target (golden EVAL-001..005) |
| `card_wallet` | carryall-card-wallet | herrera-leather | has an out-of-stock variant for the OOS path |
| `belt` | field-belt | herrera-leather | made-to-order returns edge (store-specific policy) |

### 1.3 Variants / SKUs (resolved by sku — chosen to span inventory edges)

| Handle | SKU | qty | restock | Edge state |
|---|---|---|---|---|
| `mug_in_stock` | SOL-MUG-SAGE | 24 | — | happy add-to-cart / checkout |
| `mug_low_stock` | SOL-MUG-ASH | 3 | 10d | low-stock agent answer (golden EVAL-004) |
| `wallet_in_stock` | HER-WAL-TAN | 18 | — | buyable wallet |
| `wallet_oos` | HER-WAL-ESP | 0 | 21d | `out_of_stock` (409) — J-BUY-03 edge |

### 1.4 Policies (resolved by (kind, store_slug); `key = <kind>@<store|platform>`)

The `key` format is identical to the golden dataset's `source_docs` policy keys, so
the agent layer resolves policies by the exact same string the eval set cites.

| Handle | key | Drives |
|---|---|---|
| `returns_platform` | returns@platform | return window (30d) — J-BUY-06, J-SUP-02/03 |
| `shipping_platform` | shipping@platform | shipping facts — J-SUP-02 |
| `payments_platform` | payments@platform | payment policy grounding |
| `returns_leather` | returns@herrera-leather | made-to-order returns edge (belt) |
| `care_ceramics` | care@solveig-ceramics | store-specific care answer |

### 1.5 Payment test-mode (contract-v0 §6, ADR-0021)

Two-step **intent → confirm**. The decline is purely a function of the confirm body —
no magic amount, env flag, or randomness — so J-BUY-04's failed-payment path is stable:

| Field | Value | Meaning |
|---|---|---|
| `capture_outcome` | `"captured"` | `payment-confirm outcome=captured` → success |
| `decline_outcome` | `"failed"` | **`payment-confirm outcome=failed` → deterministic decline** |
| `declined_error_code` | `payment_declined` | canonical error code on decline |
| `declined_http_status` | `402` | order stays `placed`/unpaid; payment row `failed` |

### 1.6 Return reasons

Mirrors the `ReturnReason` enum exactly (single source `app/schemas/enums.py`):
`damaged`, `not_as_described`, `wrong_item`, `no_longer_needed`, `arrived_late`,
`other`. J-BUY-06 uses an in-window reason (`damaged`); the HITL path is driven by an
order **outside** the return window (a factory delta, §4), not by the reason code.

---

## 2. Per-journey fixture matrix

Each `J-*` from `docs/qa/qa-matrix.md` §2 → the fixtures it needs → the layer(s) that
exercise it. "A" = API (httpx), "B" = browser (Playwright), "Ag" = agent eval. All 17
journeys are mapped.

| Journey | Personas | Products / variants | Policies | Factory delta (§4) | Layers |
|---|---|---|---|---|---|
| **J-BUY-01** discover/search | `buyer_primary` | `mug` | — | — | A, B, Ag |
| **J-BUY-02** compare | `buyer_primary` | `mug`, `card_wallet` | — | — | A, B, Ag |
| **J-BUY-03** add to cart | `buyer_primary` | `mug_in_stock` (+ `wallet_oos` edge) | — | `empty_cart_buyer`; `oos_at_add` | A, B, Ag |
| **J-BUY-04** checkout (happy + decline) | `buyer_primary` | `mug_in_stock` | `payments_platform` | `cart_ready_to_checkout`; **payment `decline_outcome`** | A, B |
| **J-BUY-05** track order | `buyer_primary` (+ `buyer_secondary` foreign-id edge) | `mug_in_stock` | — | `placed_order`; foreign order id | A, B |
| **J-BUY-06** return + HITL | `buyer_primary`, `support` | `mug_in_stock` | `returns_platform` | `delivered_in_window` + `delivered_outside_window` | A, B, Ag |
| **J-SEL-01** onboard seller | new seller (register) | — | — | `fresh_seller` (no store) | A, B |
| **J-SEL-02** list product | `seller_ceramics` | new variant | — | — | A, B |
| **J-SEL-03** merch nudge | `seller_ceramics` | `mug_low_stock` | — | — | A, B, Ag |
| **J-SEL-04** publish nudge | `seller_ceramics` | `mug_low_stock` | — | (audited accept) | A, B, Ag |
| **J-SEL-05** fulfil order | `seller_ceramics`, `buyer_primary` | `mug_in_stock` | — | `placed_order` against ceramics | A, B |
| **J-SUP-01** lookup order | `support` (+ `buyer_primary` order) | — | — | `placed_order`; unknown id | A, B |
| **J-SUP-02** policy-grounded assist | `support` | — | `returns_platform`, `shipping_platform` | — | A, B, Ag |
| **J-SUP-03** escalate HITL + audit | `support` | `mug_in_stock` | `returns_platform` | `delivered_outside_window` → `hitl_pending` | A, B, Ag |
| **J-ADM-01** review catalog/policies | `admin` | — | all policy handles | — | A, B |
| **J-ADM-02** adjust guardrail/policy | `admin` | — | `returns_platform` (edit) | — | A, B, Ag |
| **J-ADM-03** injection / out-of-scope refusal | `admin` / `buyer_primary` | — | — | injection probe strings | B, Ag |

**J-BUY-04 decline is explicit:** the failed-checkout path confirms the payment intent
with `PaymentConfirmRequest.outcome = "failed"` (`payment_test_mode.decline_outcome`)
→ `402 payment_declined`, payment row `failed`, order stays `placed`. This is the
single deterministic trigger from contract-v0 §6 — no other knob.

Agent-involved journeys (`J-BUY-01/02/03/06`, `J-SEL-03/04`, `J-SUP-02/03`,
`J-ADM-02/03`) each already have ≥1 labelled case in `docs/qa/eval/golden-v0.jsonl`
whose `source_docs` resolve to the same handles above.

---

## 3. The "one source" mechanism (data flow per layer)

Shared spine, built once per test on a throwaway DB:

```
migration_db (Sable, tests/db/conftest.py)   CREATE DATABASE → Alembic Config + DSN
   → seeded_db (tests/conftest.py)           upgrade head + run idempotent seed
      → handles                              resolve every handle → real seeded UUID
      → (optional factory overrides, §4)     per-test deltas on the baseline
      → tokens minted at runtime             api_client.login(persona) per layer
```

- **(a) API tests** — `api_client` is a `ContractClient` wrapping Starlette's
  `TestClient` (an `httpx.Client` over the ASGI app, no network). It speaks contract-v0:
  `{data, meta}` envelope, `Authorization: Bearer <token>`, the closed `ErrorCode` set.
  `persona_client` (parametrized by handle) logs a persona in via the real
  `POST /auth/login` and stashes the token. Resolved row ids come from the `handles`
  fixture (`handles.user_ids['buyer_primary']`, `handles.variant_ids['wallet_oos']`, …).

- **(b) Browser tests** — Playwright imports `e2e/tests/_fixtures.ts`, a typed view of
  the **same** `fixture-manifest.json`. Specs use it for seeded URLs
  (`/products/${FIXTURES.products.mug.slug}`), to pick a persona to authenticate
  (log in via the API + reuse `storageState`), and to assert known facts (the mug is
  `$34.00` = `price_minor 3400`). Selectors stay in `_selectors.ts` (the testid
  registry); `_fixtures.ts` supplies the *data*, `_selectors.ts` the *anchors*.

- **(c) Agent evals** — `golden-v0.jsonl`'s `source_docs` cite products by slug,
  variants by sku, policies by `<kind>@<scope>` — all the same natural keys the handles
  use. `test_golden_eval.py` already migrates+seeds and asserts every `source_docs`
  entry resolves to a real row; the handles are a named superset of those same keys, so
  an agent answer and an API/browser assertion reference one identical seeded mug.

**Why a generated manifest** (not direct import): the browser + agent runners can't
import Python dataclasses. `manifest.py` serializes the live handles to
`fixture-manifest.json`; the spine test asserts the on-disk JSON equals
`build_manifest()`, so editing `handles.py` without regenerating fails CI rather than
drifting the non-Python layers. Regenerate with `python -m tests.fixtures.manifest`.

**Tokens are runtime, not in the manifest.** The manifest carries *identity*
(email + test password); each layer turns that into a Bearer token at run time via
`/auth/login`. Nothing long-lived or secret is committed.

---

## 4. Factories vs seed

**Seed = the stable baseline** (idempotent, shared, never mutated by a test).
**Factories = per-test deltas** for state the static seed can't give — anything needing
isolation or a specific edge the seed shouldn't bake in permanently. Factories build on
top of `seeded_db` inside the test's own throwaway DB, so they never leak.

Factory set the journeys need (Week-2 build, as handlers land — specified here):

| Factory | Produces | Needed by |
|---|---|---|
| `empty_cart_buyer` | a buyer with a guaranteed-empty open cart | J-BUY-03 (clean add), `empty_cart` checkout edge |
| `cart_ready_to_checkout` | a cart with `mug_in_stock` × N, ready to convert | J-BUY-04 happy + decline |
| `placed_order` | a converted order in `placed` for a given buyer/store | J-BUY-05, J-SEL-05, J-SUP-01 |
| `delivered_in_window` | a delivered order **inside** the 30d return window | J-BUY-06 happy return |
| `delivered_outside_window` | a delivered order **outside** the window → direct return `409`, agent path → `hitl_pending` | J-BUY-06 / J-SUP-03 HITL |
| `oos_at_add` | flip a variant to qty 0 between recommend and add | J-BUY-03 edge (`out_of_stock`) |
| `fresh_seller` | a registered seller with **no** store profile | J-SEL-01 (incomplete profile blocks publish) |
| `foreign_order_id` | an order owned by `buyer_secondary` | J-BUY-05 / J-SUP-01 not-found/not-visible edge |

Rule of thumb: if two tests would fight over the same mutable row, it's a factory; if
it's a stable reference everyone reads, it's a seed handle. `wallet_oos` is a **seed**
handle (a permanently-OOS SKU the seed already carries); `oos_at_add` is a **factory**
(mutating an otherwise in-stock variant mid-flow).

> The factories are specified but not yet executable — they depend on Week-2 cart/order
> handlers. The spine (seed + handles + API client) is executable today (§5).

---

## 5. Scaffolding shipped today

| Path | What |
|---|---|
| `api/tests/fixtures/handles.py` | canonical catalog as typed handles, derived from the seed |
| `api/tests/fixtures/manifest.py` | emits `fixture-manifest.json` for non-Python layers |
| `api/tests/fixtures/fixture-manifest.json` | generated, committed; the browser/agent source |
| `api/tests/conftest.py` | `seeded_db`, `handles`, `api_client`, `persona_client` fixtures |
| `api/tests/fixtures/test_fixture_spine.py` | proves the spine (static + seed-resolve + login) |
| `e2e/tests/_fixtures.ts` | typed browser-layer import of the manifest |

**Test command** (throwaway DB on alt host port, per the day's DB note):

```bash
docker run -d --name hearth-fixture-db -e POSTGRES_PASSWORD=CHANGE_ME \
  -p 55444:5432 pgvector/pgvector:pg16
TEST_DATABASE_URL="postgresql+psycopg://postgres:CHANGE_ME@localhost:55444/postgres" \
DATABASE_URL="$TEST_DATABASE_URL" \
  .venv/bin/pytest tests/fixtures/ -q
```

Result today: **8 passed, 6 xfailed** — the 6 xfails are the per-persona `/auth/login`
checks, cleanly deferred until Week-2's auth handler lands (the route is a 501 contract
stub now). The spine — migrate → seed → every handle resolves to a real row → manifest
matches live handles → API client mints sessions per the contract shape — is proven.
`ruff` + `mypy --strict` clean.

---

## 6. Risks / notes (not blocking)

- **No passwords in the seed.** The fixture contract pins one test password per persona;
  Week-2 auth-backed seeding must write those exact credentials, or `persona_client`
  stays xfail. Flagged for Orion/Echo (auth handler) — do not edit the seed for this
  in Day-6 (Sable owns the seed).
- **Factories depend on Week-2 handlers.** §4 is specified but only the baseline spine
  runs today; the order/cart/return factories land with their endpoints.
- **`store_id` on order_items** (contract-v0 §4.3 open item): `J-SEL-05` /
  `placed_order`-against-a-store relies on the `variant → product → store_id` join,
  which breaks for a deleted variant. Fine for v0 seed data (no deletes); noted.
- **Manifest is a generated artifact.** It's committed so the browser/agent layers have
  zero-setup access, but it must be regenerated when `handles.py` changes — the spine
  test enforces this, so a stale manifest fails CI rather than drifting silently.
