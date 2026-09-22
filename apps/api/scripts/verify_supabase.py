"""Real execution-based Supabase/Postgres verification — uses the app's own
SQLAlchemy engine (mangrove_ai.db), never psql or a hand-rolled connection,
so this checks exactly what the running FastAPI app actually connects with.

Never prints DATABASE_URL or any credential value — only pass/fail facts
about the live connection. Run with the app's real .env in place:

    cd apps/api && source .venv/bin/activate && python scripts/verify_supabase.py

Exits 0 if every check passes, 1 otherwise, and always prints a report
covering: connection, PostGIS, pgvector, migration status (every CREATE
TABLE found in db/migrations/*.sql present in information_schema.tables),
and a real write/read/rollback round trip.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from sqlalchemy import text  # noqa: E402

MIGRATIONS_DIR = _API_ROOT.parent.parent / "db" / "migrations"


def _expected_tables() -> set[str]:
    names: set[str] = set()
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        for m in re.finditer(r"CREATE TABLE\s+(?:IF NOT EXISTS\s+)?(\w+)", f.read_text(), re.IGNORECASE):
            names.add(m.group(1).lower())
    return names


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    try:
        from mangrove_ai.db import engine
    except Exception as e:
        print(f"CONNECTION: FAIL — could not import mangrove_ai.db.engine: {e}")
        return 1

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        results.append(("CONNECTION", True, "SELECT 1 succeeded via the app's own SQLAlchemy engine"))
    except Exception as e:
        results.append(("CONNECTION", False, f"{type(e).__name__}: {e}"))
        _report(results)
        return 1

    with engine.connect() as conn:
        try:
            pg_version = conn.execute(text("SHOW server_version")).scalar()
            results.append(("POSTGRESQL", True, f"server_version={pg_version}"))
        except Exception as e:
            results.append(("POSTGRESQL", False, str(e)))

        try:
            postgis_version = conn.execute(text("SELECT PostGIS_Version()")).scalar()
            results.append(("POSTGIS", True, f"PostGIS_Version()={postgis_version}"))
        except Exception as e:
            results.append(("POSTGIS", False, f"PostGIS_Version() failed — extension likely not installed: {e}"))

        try:
            vector_installed = conn.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            ).scalar()
            if vector_installed:
                results.append(("PGVECTOR", True, f"extension installed, version={vector_installed}"))
            else:
                results.append(("PGVECTOR", False, "CREATE EXTENSION vector has not been run on this database"))
        except Exception as e:
            results.append(("PGVECTOR", False, str(e)))

        try:
            expected = _expected_tables()
            actual = {
                r[0].lower()
                for r in conn.execute(
                    text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
                )
            }
            missing = sorted(expected - actual)
            if missing:
                results.append(("MIGRATIONS", False, f"{len(missing)} table(s) from db/migrations/*.sql missing: {missing}"))
            else:
                results.append(("MIGRATIONS", True, f"all {len(expected)} expected tables present ({len(actual)} total in public schema)"))
        except Exception as e:
            results.append(("MIGRATIONS", False, str(e)))

    try:
        with engine.connect() as conn:
            # No commit() call below: closing this connection without one
            # rolls the transaction back (SQLAlchemy 2.0 default), so this
            # proves real write access without leaving any data behind —
            # and TEMP TABLE never touches another session/schema anyway.
            conn.execute(text("CREATE TEMP TABLE _verify_supabase_probe (id INT)"))
            conn.execute(text("INSERT INTO _verify_supabase_probe (id) VALUES (1)"))
            value = conn.execute(text("SELECT id FROM _verify_supabase_probe")).scalar()
            assert value == 1
        results.append(("READ_WRITE", True, "CREATE TEMP TABLE + INSERT + SELECT round trip succeeded (connection closed without commit — no data left behind)"))
    except Exception as e:
        results.append(("READ_WRITE", False, str(e)))

    _report(results)
    return 0 if all(ok for _, ok, _ in results) else 1


def _report(results: list[tuple[str, bool, str]]) -> None:
    print()
    for name, ok, detail in results:
        print(f"{name}: {'PASS' if ok else 'FAIL'} — {detail}")
    print()


if __name__ == "__main__":
    sys.exit(main())
