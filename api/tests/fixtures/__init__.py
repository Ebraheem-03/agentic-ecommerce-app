"""Canonical E2E fixtures — the 'one source' that drives all three test layers.

US-QA-D06. This package is the single source of truth for the named handles that
the API (httpx), browser (Playwright) and agent (golden/RAGAS) layers all pin to.
The handles are *derived from* the idempotent seed (`app.db.seed.data`) — they are
references, never duplicated content. If the seed renames a SKU/slug/policy/email,
the anti-drift test in `tests/fixtures/test_fixture_spine.py` fails until the
handles are updated, so the three layers can never silently diverge.

Layout:
- ``handles.py``  — the canonical catalog: personas, products, variants, policies,
  return reasons, and the payment test-mode switch, as typed Python handles.
- ``manifest.py`` — emits the catalog as a plain dict / JSON file so the browser
  (``e2e/``) and agent eval layers can import the SAME definition without Python.
- ``conftest.py``-level fixtures live in ``tests/conftest.py`` (``seeded_db``,
  ``api_client``, ``persona_client``) so every test module can request them.
"""

from __future__ import annotations

from tests.fixtures.handles import (
    PERSONAS,
    POLICY_HANDLES,
    PRODUCT_HANDLES,
    RETURN_REASONS,
    VARIANT_HANDLES,
    PaymentTestMode,
    Persona,
    PolicyHandle,
    ProductHandle,
    VariantHandle,
)

__all__ = [
    "PERSONAS",
    "POLICY_HANDLES",
    "PRODUCT_HANDLES",
    "RETURN_REASONS",
    "VARIANT_HANDLES",
    "PaymentTestMode",
    "Persona",
    "PolicyHandle",
    "ProductHandle",
    "VariantHandle",
]
