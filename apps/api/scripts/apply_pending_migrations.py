"""Applies db/migrations/100, 101, 102 using the app's own SQLAlchemy
engine — not psql, matching scripts/verify_supabase.py's approach, since
psql was unreliable in this project's Windows setup before.

Safe to run more than once: each step checks whether it's already applied
before running, so re-running this after a partial failure won't error on
"column already exists" or duplicate-insert the seeded AOIs.

Usage (from apps/api, with your real .env in place):
    python scripts/apply_pending_migrations.py

Never prints DATABASE_URL or any credential value.
"""

from __future__ import annotations

import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from sqlalchemy import text  # noqa: E402

MIGRATIONS_DIR = _API_ROOT.parent.parent / "db" / "migrations"


def _migration_100(conn) -> str:
    existing = conn.execute(
        text("SELECT count(*) FROM aois WHERE name IN "
             "('Sandspit (Karachi coastal mangroves, approximate)', 'Keti Bunder / Indus Delta (approximate)')")
    ).scalar()
    if existing == 2:
        return "already applied (both named AOIs present) — skipped"
    conn.execute(text((MIGRATIONS_DIR / "100_seed_additional_karachi_aois.sql").read_text()))
    return "applied"


def _migration_101(conn) -> str:
    has_column = conn.execute(
        text("SELECT count(*) FROM information_schema.columns "
             "WHERE table_name = 'models' AND column_name = 'is_synthetic'")
    ).scalar()
    if has_column:
        return "already applied (models.is_synthetic exists) — skipped"
    conn.execute(text((MIGRATIONS_DIR / "101_model_provenance.sql").read_text()))
    return "applied"


def _migration_102(conn) -> str:
    # ALTER COLUMN ... SET DEFAULT and the UPDATE are both naturally
    # idempotent (no error, no-op on a second run), so just run it.
    conn.execute(text((MIGRATIONS_DIR / "102_fix_cgmd_asset_default.sql").read_text()))
    return "applied (idempotent — safe even if already run)"


STEPS = [
    ("100_seed_additional_karachi_aois.sql", _migration_100),
    ("101_model_provenance.sql", _migration_101),
    ("102_fix_cgmd_asset_default.sql", _migration_102),
]


def main() -> int:
    try:
        from mangrove_ai.db import engine
    except Exception as e:
        print(f"FAILED to import mangrove_ai.db.engine: {e}")
        return 1

    print()
    for name, fn in STEPS:
        try:
            with engine.begin() as conn:
                result = fn(conn)
            print(f"{name}: OK — {result}")
        except Exception as e:
            print(f"{name}: FAILED — {type(e).__name__}: {e}")
            print("\nStopped here — fix the error above before re-running (safe to re-run from the start).")
            return 1
    print("\nAll pending migrations applied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
