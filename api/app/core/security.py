"""Password hashing + opaque session-token primitives (US-E4-04, ADR-0023).

Two distinct cryptographic concerns, intentionally using two different algorithms:

* **Passwords** are *low-entropy* user secrets, so they get a slow, memory-hard hash:
  **argon2id** via ``argon2-cffi`` (``PasswordHasher`` with library defaults). The full
  PHC string (algo + params + salt + hash) is stored in ``users.password_hash``. Raw
  passwords are never logged or persisted.
* **Session tokens** are *high-entropy* random strings (``secrets.token_urlsafe(32)``,
  ≈256 bits), so a fast hash (**SHA-256**) is correct — argon2 would only add latency to
  every authenticated request for no security gain. Only the SHA-256 *digest* is stored
  in ``sessions.token_hash``; the raw token is shown to the client once and is never
  re-derivable from the database.
"""

from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, VerifyMismatchError

# Library-default parameters (OWASP-aligned, memory-hard, tunable). One shared instance.
_hasher = PasswordHasher()

# A pre-computed argon2 hash of a throwaway value. Verifying a supplied password against
# this when an account has no stored hash keeps login timing roughly constant (no fast
# "user not found" early-out that an attacker could measure to enumerate accounts).
_DUMMY_HASH = _hasher.hash("hearth-dummy-verify-target")


def hash_password(password: str) -> str:
    """Return the argon2id PHC string for ``password`` (store this verbatim)."""
    return _hasher.hash(password)


def verify_password(stored_hash: str | None, password: str) -> bool:
    """Verify ``password`` against a stored argon2 PHC string.

    A ``None`` stored hash (provisioned/legacy account) is an automatic failure, but we
    still run a dummy verify so the timing matches the real-hash path and does not leak
    whether the account exists / has a credential.
    """
    if stored_hash is None:
        try:
            _hasher.verify(_DUMMY_HASH, password)
        except (VerifyMismatchError, Argon2Error):
            pass
        return False
    try:
        return _hasher.verify(stored_hash, password)
    except (VerifyMismatchError, Argon2Error):
        return False


def mint_session_token() -> str:
    """Generate a fresh high-entropy opaque session token (returned to the client once)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 hex digest of a session token — the value stored in ``sessions.token_hash``."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
