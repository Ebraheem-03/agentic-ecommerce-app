# 0023 — Auth implementation: argon2id hashing, sliding session tokens, email-verify gate (US-E4-04)

Status: accepted · 2026-06-17 · Owner: Atlas (decision) / Orion (build)

## Context
Contract-v0 **Decision #1** (ADR-0021) ratified the auth *mechanism*: an opaque,
server-side **session token** backed by `sessions(token_hash, expires_at)`, sent as
`Authorization: Bearer <token>`, logout = row delete (instant revocation), **not a JWT**.
That left three implementation calls open for Day 9 (the US-E4-04 `[REVIEW]`), which the
human ratified on 2026-06-17:

1. how passwords are hashed,
2. session-token lifetime + renewal behavior,
3. the shape of the email-verification stub (and whether it gates login).

> Note: the Week-2 plan row for US-E4-04 loosely reads "JWT sessions". The contract
> overrides the plan — we build opaque session tokens, **not** JWTs. This ADR records the
> binding choices.

## Decisions
- **Password hashing — argon2id** via `argon2-cffi` (`PasswordHasher`, library defaults).
  OWASP's current best-practice (memory-hard, tunable); chosen over bcrypt/pbkdf2 to
  demonstrate modern password storage. `users.password_hash` (already nullable `Text`)
  stores the full PHC-string (algo + params + salt + hash). Raw passwords are never
  persisted or logged. Verify on login; treat a `None` hash (provisioned/legacy accounts)
  as an automatic auth failure (no timing shortcut — still run a dummy verify where cheap).

- **Session token — sliding 7-day expiry.** The token is high-entropy
  `secrets.token_urlsafe(32)` (≈256 bits); we store **only its SHA-256** in
  `sessions.token_hash` (the raw token is returned once, never re-derivable from the DB).
  Because the token is already high-entropy random, a fast hash (SHA-256) is correct here —
  argon2 is for *low-entropy* passwords, not for opaque tokens. `expires_at = now + 7d` at
  mint; **each authenticated request bumps `expires_at` forward by 7d** (sliding window), so
  active users stay signed in and idle ones expire. No separate refresh endpoint — renewal
  is implicit in use, which keeps the "opaque token, delete-to-revoke" model intact and
  gives US-QA-D09 a real expiry path to assert. Expired rows are treated as
  `401 unauthenticated` and may be lazily deleted.

- **Email verification — real column, login gated.** New migration **0004** adds
  `users.email_verified boolean NOT NULL DEFAULT false`. Register creates the account
  **unverified** and still returns a session (so the client has identity), but a
  `POST /auth/verify` **stub** (no email is actually sent — demo only) flips the flag, and
  **login is denied with `403 forbidden` while `email_verified = false`**. This is the
  realistic option the human chose over a pure no-op.
  - **Consequence the seed must honor:** gating login means the seeded personas would be
    *unable* to log in (defeating the 6 fixture xfails) unless seeding marks them verified.
    Therefore **auth-backed seeding sets `email_verified = true` for every seeded persona**
    in addition to writing the per-persona password hash (`HEARTH_TEST_PASSWORD`). This is
    the wire that flips the 6 `/auth/login` xfails (`test_fixture_spine.py`) green.

## Consequences
- New runtime dep: `argon2-cffi` (add to `api/pyproject.toml`). One new migration `0004`
  (additive, non-breaking; default `false` so a re-applied schema is deterministic).
- `403 forbidden` (code `forbidden`) carries the "unverified" denial; bad credentials and
  missing/expired tokens stay `401 unauthenticated` per the error catalog — distinct codes,
  so QA can assert each path.
- Auth resolution (Bearer → session → user, with sliding bump) becomes a shared FastAPI
  dependency reused by every protected route and by US-E4-05's scope middleware (agents act
  under the resolving user's scope).
- The `[REVIEW] §5` open item in `docs/api/contract-v0.md` §1.3 is now closed by this ADR.
