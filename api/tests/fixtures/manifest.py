"""Emit the canonical fixture catalog as a plain dict / JSON for non-Python layers.

US-QA-D06. The API layer imports the typed handles directly from ``handles.py``.
The **browser** (Playwright, ``e2e/``) and **agent eval** layers can't import Python
dataclasses, so they read the SAME definition from a generated JSON manifest:

    api/tests/fixtures/fixture-manifest.json   (generated, committed)

Regenerate after editing ``handles.py``::

    python -m tests.fixtures.manifest        # writes the JSON next to this file

The spine test (`test_fixture_spine.py`) also asserts the on-disk JSON matches the
live handles, so a stale manifest is a test failure, not a silent drift.

What the manifest does NOT contain: session tokens. Tokens are minted at runtime
(login per persona) by each layer's runner — the manifest carries the *identity*
(email + test password), and the runtime step turns that into a Bearer token.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.fixtures.handles import (
    PAYMENT_TEST_MODE,
    PERSONAS,
    POLICY_HANDLES,
    PRODUCT_HANDLES,
    RETURN_REASONS,
    VARIANT_HANDLES,
)

MANIFEST_PATH = Path(__file__).resolve().parent / "fixture-manifest.json"


def build_manifest() -> dict[str, Any]:
    """Build the layer-agnostic manifest dict from the live handles."""
    return {
        "_about": (
            "Canonical Hearth E2E fixtures (US-QA-D06). One source for API, browser, "
            "and agent test layers. Generated from api/tests/fixtures/handles.py — "
            "do not hand-edit; run `python -m tests.fixtures.manifest`."
        ),
        "personas": {
            p.handle: {
                "email": p.email,
                "display_name": p.display_name,
                "role": str(p.role),
                "password": p.password,
            }
            for p in PERSONAS.values()
        },
        "products": {
            p.handle: {"slug": p.slug, "title": p.title, "store_slug": p.store_slug}
            for p in PRODUCT_HANDLES.values()
        },
        "variants": {
            v.handle: {
                "sku": v.sku,
                "product_slug": v.product_slug,
                "price_minor": v.price_minor,
                "qty_on_hand": v.qty_on_hand,
                "restock_eta_days": v.restock_eta_days,
                "in_stock": v.in_stock,
            }
            for v in VARIANT_HANDLES.values()
        },
        "policies": {
            p.handle: {"key": p.key, "kind": p.kind, "store_slug": p.store_slug, "title": p.title}
            for p in POLICY_HANDLES.values()
        },
        "return_reasons": [str(r) for r in RETURN_REASONS],
        "payment_test_mode": {
            "capture_outcome": PAYMENT_TEST_MODE.capture_outcome,
            "decline_outcome": PAYMENT_TEST_MODE.decline_outcome,
            "declined_error_code": PAYMENT_TEST_MODE.declined_error_code,
            "declined_http_status": PAYMENT_TEST_MODE.declined_http_status,
        },
    }


def write_manifest(path: Path = MANIFEST_PATH) -> Path:
    """Serialize the manifest to disk (stable key order, trailing newline)."""
    path.write_text(
        json.dumps(build_manifest(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def main() -> None:
    out = write_manifest()
    print(f"wrote fixture manifest -> {out}")


if __name__ == "__main__":
    main()
