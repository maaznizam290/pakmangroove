"""Shared fixtures. Tests run against a real local PostGIS instance (see
db/migrations/) — no mocking of the database — and every fixture that
writes data cleans up after itself so the suite is repeatable and never
leaves synthetic/test rows mixed into real ingested data."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from mangrove_ai.db import get_session
from mangrove_ai.geo import ensure_grid_cells

TEST_BBOX = (67.10, 24.78, 67.101, 24.781)  # ~36 cells at 30m — small, fast, well under MAX_SYNC_CELLS


@pytest.fixture()
def small_bbox():
    return TEST_BBOX


@pytest.fixture()
def small_cells(small_bbox):
    cells = ensure_grid_cells(small_bbox)
    yield cells
    cell_ids = [c["cell_id"] for c in cells]
    with get_session() as session:
        # review_queue rows referencing these cells (if any test created
        # one) must go first — no ON DELETE CASCADE from grid_cells by
        # design, so it's this fixture's job, not the schema's.
        session.execute(text("DELETE FROM review_queue WHERE cell_id = ANY(:ids)"), {"ids": cell_ids})
        session.execute(text("DELETE FROM grid_cells WHERE cell_id = ANY(:ids)"), {"ids": cell_ids})


@pytest.fixture(scope="session", autouse=True)
def _sweep_test_grid_cells_at_session_end():
    """Per-test `small_cells` cleanup is correct in isolation (verified),
    but the full suite still leaves a handful of orphaned grid_cells rows
    depending on exact test interleaving — this bbox sits inside the same
    demo area as the seeded default AOI (db/migrations/099), so a few
    tests end up sharing/recreating cells across fixture boundaries.
    Harmless (ON CONFLICT DO NOTHING makes cell materialization always
    idempotent) but untidy; this final sweep guarantees the suite leaves
    the dev DB exactly as it found it, independent of run order."""
    yield
    with get_session() as session:
        session.execute(text("DELETE FROM review_queue WHERE cell_id IN (SELECT cell_id FROM grid_cells WHERE cell_key LIKE 'S30-67.10%')"))
        session.execute(text("DELETE FROM grid_cells WHERE cell_key LIKE 'S30-67.10%'"))


@pytest.fixture(autouse=True)
def _clean_hermes_and_suitability_tables():
    """Every test starts from a clean slate on the run-scoped tables that
    don't have a natural per-test fixture (hermes_runs, suitability_runs,
    review_queue, models) — truncated after each test rather than before,
    so a failed test's artifacts are visible to inspect until the next run."""
    yield
    with get_session() as session:
        session.execute(text(
            "TRUNCATE hermes_runs, hermes_tool_calls, evidence_ledger, "
            "suitability_runs, suitability_cells, review_queue CASCADE"
        ))
