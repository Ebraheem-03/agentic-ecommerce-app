"""QA test fixtures.

Re-export Sable's throwaway-DB fixture so the golden-eval seed-resolve test
(`test_golden_eval.py`) can spin up a migrated + seeded disposable Postgres the
same way the DB tests do, without duplicating the create/drop machinery.
"""

from __future__ import annotations

from tests.db.conftest import migration_db, open_conn

__all__ = ["migration_db", "open_conn"]
