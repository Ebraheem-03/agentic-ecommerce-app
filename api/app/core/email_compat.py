"""Allow RFC 6761 ``.test`` addresses through ``EmailStr`` validation (demo only).

The whole fixture/seed catalog identifies personas with reserved-TLD addresses like
``ada@buyers.hearth.test`` (RFC 6761 ``.test`` — the correct TLD for examples/tests, and
the one the QA fixture spine pins to). By default ``email-validator`` (used by Pydantic's
``EmailStr``) rejects reserved/special-use domains, so ``/auth/register`` + ``/auth/login``
would 422 on every seeded persona.

``email-validator`` documents removing an entry from ``SPECIAL_USE_DOMAIN_NAMES`` as the
supported way to permit it in a test/demo environment. We drop only ``test`` — every other
special-use domain (``localhost``, ``invalid``, ``example``, …) stays rejected. Importing
this module applies the tweak; ``app.main`` imports it at startup. See ADR-0024.
"""

from __future__ import annotations

import email_validator


def allow_test_tld() -> None:
    """Permit the RFC 6761 ``.test`` TLD in email validation (idempotent)."""
    if "test" in email_validator.SPECIAL_USE_DOMAIN_NAMES:
        email_validator.SPECIAL_USE_DOMAIN_NAMES.remove("test")


allow_test_tld()
