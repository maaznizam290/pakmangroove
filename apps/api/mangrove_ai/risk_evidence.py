"""Bundal ecological-risk evidence linkage.

Per the build spec: heavy-metal observations stay attached to their actual
sampling location. This module only ever answers a proximity question —
"is there a real sampled point near this cell" — and returns a flag plus
the actual sample rows, never a continuous/interpolated pollution value
for the queried cell itself.
"""

from __future__ import annotations

from sqlalchemy import text

from mangrove_ai.config import settings
from mangrove_ai.db import get_session

LOCAL_RISK_FLAG = "LOCAL_ECOLOGICAL_RISK_EVIDENCE_AVAILABLE"

_NEARBY_SAMPLES_SQL = text("""
    SELECT sample_id, study_source, sample_label, metal, igeo, bcf, tf, species, source_page,
           ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS distance_m
    FROM ecological_risk_samples
    WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius_m)
    ORDER BY distance_m ASC
""")


_BATCH_NEARBY_SQL = text("""
    SELECT DISTINCT g.cell_id
    FROM grid_cells g
    JOIN ecological_risk_samples s
      ON ST_DWithin(g.centroid::geography, s.geom::geography, :radius_m)
    WHERE g.cell_id = ANY(:cell_ids)
""")


def local_risk_evidence_batch(cell_ids: list[int], radius_m: float | None = None) -> set[int]:
    """One-query version of local_risk_evidence for scoring a whole AOI —
    used by calculate_restoration_suitability instead of a per-cell round
    trip. Returns the subset of cell_ids within radius_m of any actually
    sampled ecological_risk_samples point."""
    if not cell_ids:
        return set()
    radius_m = radius_m if radius_m is not None else settings.ecological_risk_proximity_m
    with get_session() as session:
        rows = session.execute(_BATCH_NEARBY_SQL, {"cell_ids": cell_ids, "radius_m": radius_m}).mappings().all()
    return {r["cell_id"] for r in rows}


def local_risk_evidence(lon: float, lat: float, radius_m: float | None = None) -> dict:
    """Returns {"flag": bool, "samples": [...]}. `samples` lists the actual
    nearby sampled rows (each still tied to its own coordinates/metal/Igeo)
    — nothing here is averaged, interpolated, or assigned to (lon, lat)
    itself."""
    radius_m = radius_m if radius_m is not None else settings.ecological_risk_proximity_m
    with get_session() as session:
        rows = session.execute(_NEARBY_SAMPLES_SQL, {"lon": lon, "lat": lat, "radius_m": radius_m}).mappings().all()

    samples = [dict(r) for r in rows]
    return {
        "flag": LOCAL_RISK_FLAG if samples else None,
        "has_evidence": bool(samples),
        "samples": samples,
        "radius_m": radius_m,
        "note": (
            "Evidence limited to actually-sampled points within radius_m; "
            "not an interpolated citywide pollution estimate."
        ),
    }
