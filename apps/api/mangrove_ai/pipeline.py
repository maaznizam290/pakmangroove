"""GEE composite -> spectral indices -> spectral_index_values pipeline.

The one place that turns a live Earth Engine Sentinel-2 composite into
per-cell spectral index rows in Postgres, so calculate_health_indicators
(mangrove_ai.tools) has real data to read instead of an empty table.

Every value written here is either a real ee.Reducer.mean() sample
(gee_client.sample_bands_at_cells) or a real numpy formula from
mangrove_ai.indices applied to that sample. A grid cell where GEE returns
no valid pixel for any required band (cloud-masked throughout the period,
outside the composite's clipped AOI, or a scene gap) is skipped entirely,
never zero-filled — "no data" and "computed as 0" must stay distinguishable.
"""

from __future__ import annotations

import json
from datetime import date

import numpy as np
from sqlalchemy import text

from mangrove_ai.config import settings
from mangrove_ai.db import get_session
from mangrove_ai.gee_client import _S2_BAND_MAP, CompositeRequest, GEENotConfiguredError, gee_client
from mangrove_ai.geo import ensure_grid_cells, resolve_aoi
from mangrove_ai.indices import compute_all_indices

_CODE_TO_NAME = {code: name for name, code in _S2_BAND_MAP.items()}

_INSERT_COMPOSITE_SQL = text(
    """INSERT INTO sentinel2_composites
           (aoi_id, period_start, period_end, composite_type, cloud_prob_max, ee_collection)
       VALUES (:aoi_id, :period_start, :period_end, :composite_type, :cloud_prob_max, :ee_collection)
       RETURNING composite_id"""
)

_UPSERT_INDEX_VALUE_SQL = text(
    """INSERT INTO spectral_index_values (cell_id, composite_id, index_name, value)
       VALUES (:cell_id, :composite_id, :index_name, :value)
       ON CONFLICT (cell_id, composite_id, index_name) DO UPDATE SET value = EXCLUDED.value"""
)

# Idempotency check: a composite already materialized for this exact named
# AOI/period/type has its indices already sitting in spectral_index_values —
# reuse it instead of re-hitting the live (quota-limited, slow) GEE API.
# Scoped to aoi_id, not bbox: an arbitrary drawn bbox has no stable identity
# to cache against in sentinel2_composites (which only stores aoi_id), so
# only named-AOI calls (the default/seeded AOIs the frontend actually
# repeats) get this fast path.
_FIND_EXISTING_COMPOSITE_SQL = text(
    """SELECT composite_id FROM sentinel2_composites
       WHERE aoi_id = :aoi_id AND period_start = :period_start AND period_end = :period_end
         AND composite_type = :composite_type
       ORDER BY computed_at DESC LIMIT 1"""
)

_CACHED_INDEX_VALUE_COUNTS_SQL = text(
    """SELECT index_name, count(DISTINCT cell_id) AS cell_count, count(*) AS row_count
       FROM spectral_index_values
       WHERE composite_id = :composite_id AND cell_id = ANY(:cell_ids)
       GROUP BY index_name"""
)


def _try_cached_composite(
    aoi_id: str, period_start: date, period_end: date, composite_type: str,
    cell_ids: list[int], cell_count: int,
) -> dict | None:
    """Returns a materialize_composite-shaped summary reusing an existing
    sentinel2_composites row for this exact AOI/period/type if one already
    has spectral_index_values rows covering this AOI's current cells, else
    None (caller proceeds to build a fresh composite via GEE)."""
    with get_session() as session:
        existing_id = session.execute(_FIND_EXISTING_COMPOSITE_SQL, {
            "aoi_id": aoi_id, "period_start": period_start, "period_end": period_end,
            "composite_type": composite_type,
        }).scalar()
        if not existing_id:
            return None
        counts = session.execute(_CACHED_INDEX_VALUE_COUNTS_SQL, {
            "composite_id": existing_id, "cell_ids": cell_ids,
        }).mappings().all()

    if not counts:
        return None

    return {
        "composite_id": str(existing_id),
        "cell_count": cell_count,
        "cells_with_data": max(row["cell_count"] for row in counts),
        "indices_written": sum(row["row_count"] for row in counts),
        "indices_computed": [row["index_name"] for row in counts],
        "cached": True,
    }


def materialize_composite(
    aoi_id: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    composite_type: str = "annual",
) -> dict:
    """Builds a real Sentinel-2 composite for the AOI, samples spectral
    bands at every materialized grid-cell centroid, computes spectral
    indices with mangrove_ai.indices, and writes them into
    spectral_index_values.

    Raises GEENotConfiguredError if no GEE credentials are configured (see
    gee_client.GEEClient.is_configured) — never silently returns or writes
    fabricated rows. Raises mangrove_ai.geo.AOITooLargeError for an AOI
    over MAX_SYNC_CELLS, same as every other grid-scoped tool.
    """
    if not gee_client.is_configured:
        raise GEENotConfiguredError(
            "GEE_SERVICE_ACCOUNT_KEY_PATH / GEE_SERVICE_ACCOUNT_EMAIL are not set. "
            "No live Earth Engine call was made — this is not a fabricated result."
        )

    aoi = resolve_aoi(aoi_id, bbox)
    cells = ensure_grid_cells(aoi["bounds"])
    if not cells:
        return {"composite_id": None, "cell_count": 0, "cells_with_data": 0, "indices_written": 0, "indices_computed": []}

    resolved_period_start = period_start or date(2023, 1, 1)
    resolved_period_end = period_end or date(2023, 12, 31)
    cell_ids = [c["cell_id"] for c in cells]

    if aoi["aoi_id"]:
        cached = _try_cached_composite(aoi["aoi_id"], resolved_period_start, resolved_period_end, composite_type, cell_ids, len(cells))
        if cached is not None:
            return cached

    request = CompositeRequest(
        aoi_geojson=json.loads(aoi["geojson_str"]),
        period_start=resolved_period_start,
        period_end=resolved_period_end,
        composite_type=composite_type,
    )
    composite = gee_client.build_annual_composite(request)

    cell_points = [{"type": "Point", "coordinates": [c["lon"], c["lat"]]} for c in cells]
    features = gee_client.sample_bands_at_cells(composite, cell_points)
    by_idx = {f["properties"]["idx"]: f["properties"] for f in features}

    with get_session() as session:
        composite_id = session.execute(
            _INSERT_COMPOSITE_SQL,
            {
                "aoi_id": aoi["aoi_id"],
                "period_start": request.period_start,
                "period_end": request.period_end,
                "composite_type": request.composite_type,
                "cloud_prob_max": request.cloud_prob_max,
                "ee_collection": settings.s2_sr_collection,
            },
        ).scalar()

    band_codes = list(_S2_BAND_MAP.values())
    raw_bands: dict[str, list[float | None]] = {code: [] for code in band_codes}
    for i in range(len(cells)):
        props = by_idx.get(i, {})
        for code in band_codes:
            raw_bands[code].append(props.get(code))

    # A masked-out / no-valid-pixel cell comes back as None from
    # reduceRegions — drop it rather than let a 0.0 masquerade as a real
    # reflectance sample.
    valid_indices = [
        i for i in range(len(cells))
        if all(raw_bands[code][i] is not None for code in band_codes)
    ]

    if not valid_indices:
        return {
            "composite_id": str(composite_id), "cell_count": len(cells),
            "cells_with_data": 0, "indices_written": 0, "indices_computed": [],
        }

    bands = {
        _CODE_TO_NAME[code]: np.array([raw_bands[code][i] for i in valid_indices], dtype=float)
        for code in band_codes
    }
    computed = compute_all_indices(bands)

    rows_to_insert = [
        {"cell_id": cell_ids[i], "composite_id": composite_id, "index_name": index_name, "value": float(values[j])}
        for index_name, values in computed.items()
        for j, i in enumerate(valid_indices)
    ]

    with get_session() as session:
        if rows_to_insert:
            session.execute(_UPSERT_INDEX_VALUE_SQL, rows_to_insert)

    return {
        "composite_id": str(composite_id),
        "cell_count": len(cells),
        "cells_with_data": len(valid_indices),
        "indices_written": len(rows_to_insert),
        "indices_computed": list(computed.keys()),
    }
