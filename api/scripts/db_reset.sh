#!/usr/bin/env bash
# =============================================================================
# db_reset.sh — repeatable, GUARDED local dev DB reset (US-QA-D04).
#
# Drops + recreates a clean dev database and re-applies all Alembic migrations to
# `head`. This is the "seed reset contract" hook: US-E3-03 (seed) plugs its seed
# step in at the marked point below — reset stays idempotent and seed stays its own
# concern.
#
# SAFETY: refuses to run unless the target DB name matches a dev/test pattern
# (default: contains `dev`, `test`, or `local`), UNLESS --force is passed. This
# guards against accidentally wiping a staging/prod DB whose URL is in the env.
#
# Usage:
#   api/scripts/db_reset.sh                     # uses $DATABASE_URL (or compose default)
#   DATABASE_URL=... api/scripts/db_reset.sh    # explicit target
#   api/scripts/db_reset.sh --force             # bypass the name guard (you asked for it)
#   DB_RESET_ALLOW='dev|test|sandbox' api/scripts/db_reset.sh   # custom allow-pattern
#
# No credentials are baked in: the connection comes from $DATABASE_URL (see
# repo-root .env.example). See docs/qa/db-migration-test-plan.md and ADR-0019.
# =============================================================================
set -euo pipefail

FORCE=0
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

# Resolve api/ root from this script's location so it works from any CWD.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Default to the docker-compose local URL if nothing is set. CHANGE_ME is a
# placeholder password (matches .env.example) — set a real one in .env.
DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://postgres:CHANGE_ME@localhost:5432/agentic_ecommerce}"

# Parse the libpq pieces out of the SQLAlchemy URL with Python (handles the
# +psycopg suffix, ports, and password-less forms robustly).
read -r DB_USER DB_PASS DB_HOST DB_PORT DB_NAME < <(
  DATABASE_URL="$DATABASE_URL" python3 - <<'PY'
import os
from urllib.parse import urlsplit, unquote
u = urlsplit(os.environ["DATABASE_URL"])
print(
    unquote(u.username or "postgres"),
    unquote(u.password or ""),
    u.hostname or "localhost",
    u.port or 5432,
    (u.path or "/agentic_ecommerce").lstrip("/"),
)
PY
)

ALLOW_PATTERN="${DB_RESET_ALLOW:-dev|test|local}"
if [[ "$FORCE" -ne 1 ]]; then
  if [[ ! "$DB_NAME" =~ ($ALLOW_PATTERN) ]]; then
    echo "REFUSING: target DB '$DB_NAME' does not match dev/test pattern ($ALLOW_PATTERN)." >&2
    echo "If you really mean it, re-run with --force or set DB_RESET_ALLOW." >&2
    exit 1
  fi
fi

echo ">> Resetting database '$DB_NAME' on $DB_HOST:$DB_PORT (user=$DB_USER)"

# Admin commands run against the 'postgres' maintenance DB (can't drop the DB
# you're connected to). PGPASSWORD is exported only for the child psql calls.
export PGPASSWORD="$DB_PASS"
PSQL_ADMIN=(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1)

# Disconnect lingering sessions, then drop + recreate.
"${PSQL_ADMIN[@]}" -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" \
  >/dev/null
"${PSQL_ADMIN[@]}" -c "DROP DATABASE IF EXISTS \"$DB_NAME\";"
"${PSQL_ADMIN[@]}" -c "CREATE DATABASE \"$DB_NAME\";"
echo ">> Recreated clean database."

# Re-apply all migrations to head. env.py reads DATABASE_URL from the env.
echo ">> Applying Alembic migrations to head..."
( cd "$API_ROOT" && DATABASE_URL="$DATABASE_URL" alembic upgrade head )

# --- SEED RESET CONTRACT HOOK (US-E3-03) ------------------------------------
# Tomorrow's seed story plugs in here, e.g.:
#   ( cd "$API_ROOT" && DATABASE_URL="$DATABASE_URL" python -m app.db.seed )
# Keeping reset and seed separate means `db_reset.sh` stays a pure, idempotent
# schema reset; seeding is opt-in.
# ----------------------------------------------------------------------------

echo ">> Done. '$DB_NAME' is clean and migrated to head."
