"""AOI resolution and on-demand grid materialization. grid_cells starts
empty — cells are generated the first time an AOI is queried, snapped to
a fixed grid so repeated queries over overlapping areas reuse the same
cell_ids (see cell_key)."""

from __future__ import annotations

from sqlalchemy import text

from mangrove_ai.config import settings
from mangrove_ai.db import get_session

_METERS_PER_DEGREE_LAT = 111_320.0

# Synchronous grid materialization (ST_SquareGrid + per-cell INSERT) is
# only viable up to a few thousand cells — the full seeded Karachi AOI at
# 30m resolution is ~2M cells and would hang the request indefinitely.
# Matches the "BBOX size limit" / async-job design in
# docs/architecture/PAKMANG_AI_MVP_ENGINEERING_SPEC.md §3.1, simplified for
# this MVP to a hard cap with a clear error rather than a background job
# queue: draw a smaller AOI instead of waiting on an unbounded query.
MAX_SYNC_CELLS = 10_000


class AOITooLargeError(ValueError):
    def __init__(self, estimated_cells: int):
        self.estimated_cells = estimated_cells
        super().__init__(
            f"AOI would materialize ~{estimated_cells:,} cells at {settings.grid_cell_size_m}m resolution, "
            f"over the {MAX_SYNC_CELLS:,}-cell synchronous limit. Draw a smaller AOI or zoom in."
        )


def _degrees_for_cell_size(lat: float) -> float:
    import math

    return settings.grid_cell_size_m / (_METERS_PER_DEGREE_LAT * max(0.1, math.cos(math.radians(lat))))


_RESOLVE_AOI_SQL = text("SELECT ST_AsGeoJSON(geom) AS geojson, ST_XMin(geom) x0, ST_YMin(geom) y0, ST_XMax(geom) x1, ST_YMax(geom) y1 FROM aois WHERE aoi_id = :aoi_id")
_DEFAULT_AOI_SQL = text("SELECT aoi_id, ST_AsGeoJSON(geom) AS geojson, ST_XMin(geom) x0, ST_YMin(geom) y0, ST_XMax(geom) x1, ST_YMax(geom) y1 FROM aois WHERE is_default LIMIT 1")
_LIST_AOIS_SQL = text(
    """SELECT aoi_id, name, description, is_default,
              ST_XMin(geom) x0, ST_YMin(geom) y0, ST_XMax(geom) x1, ST_YMax(geom) y1
       FROM aois ORDER BY is_default DESC, name"""
)


def list_aois() -> list[dict]:
    """Every seeded/named AOI (Bundal Island default + any other named
    region, e.g. Sandspit / Keti Bunder — see db/migrations/099, 100),
    for a frontend AOI picker. User-drawn custom bboxes never appear here
    since they aren't persisted as `aois` rows."""
    with get_session() as session:
        rows = session.execute(_LIST_AOIS_SQL).mappings().all()
    return [
        {
            "aoi_id": str(r["aoi_id"]),
            "name": r["name"],
            "description": r["description"],
            "is_default": r["is_default"],
            "bounds": (r["x0"], r["y0"], r["x1"], r["y1"]),
        }
        for r in rows
    ]


def resolve_aoi(aoi_id: str | None = None, bbox: tuple[float, float, float, float] | None = None) -> dict:
    """Returns {"aoi_id": str|None, "geojson": dict, "bounds": (x0,y0,x1,y1)}.
    Exactly one of aoi_id/bbox should be given; if neither, falls back to
    the seeded default Karachi AOI."""
    with get_session() as session:
        if aoi_id:
            row = session.execute(_RESOLVE_AOI_SQL, {"aoi_id": aoi_id}).mappings().first()
            if not row:
                raise ValueError(f"No AOI found with aoi_id={aoi_id}")
            return {"aoi_id": aoi_id, "bounds": (row["x0"], row["y0"], row["x1"], row["y1"]), "geojson_str": row["geojson"]}
        if bbox:
            x0, y0, x1, y1 = bbox
            geojson = session.execute(text("SELECT ST_AsGeoJSON(ST_MakeEnvelope(:x0,:y0,:x1,:y1,4326)) AS g"),
                                       {"x0": x0, "y0": y0, "x1": x1, "y1": y1}).scalar()
            return {"aoi_id": None, "bounds": bbox, "geojson_str": geojson}
        row = session.execute(_DEFAULT_AOI_SQL).mappings().first()
        if not row:
            raise ValueError("No default AOI seeded — run db/migrations/099_seed_karachi_aoi.sql")
        return {"aoi_id": str(row["aoi_id"]), "bounds": (row["x0"], row["y0"], row["x1"], row["y1"]), "geojson_str": row["geojson"]}


_MATERIALIZE_SQL = text("""
    WITH grid AS (
        SELECT (ST_SquareGrid(:deg_size, ST_MakeEnvelope(:x0, :y0, :x1, :y1, 4326))).geom AS geom
    ),
    keyed AS (
        SELECT geom,
               'S' || :cell_size_m || '-' || round(ST_X(ST_Centroid(geom))::numeric, 6) || '-' || round(ST_Y(ST_Centroid(geom))::numeric, 6) AS cell_key
        FROM grid
    )
    INSERT INTO grid_cells (cell_key, geom, centroid, cell_size_m)
    SELECT cell_key, geom, ST_Centroid(geom), :cell_size_m FROM keyed
    ON CONFLICT (cell_key) DO NOTHING
    RETURNING cell_id
""")

_SELECT_CELLS_SQL = text("""
    SELECT cell_id, ST_X(centroid) AS lon, ST_Y(centroid) AS lat
    FROM grid_cells
    WHERE ST_Intersects(geom, ST_MakeEnvelope(:x0, :y0, :x1, :y1, 4326))
""")


def ensure_grid_cells(bounds: tuple[float, float, float, float]) -> list[dict]:
    """Materializes (idempotently) grid cells covering `bounds` and returns
    every cell (existing + newly created) with its id and centroid.
    Raises AOITooLargeError before touching the DB if the estimated cell
    count exceeds MAX_SYNC_CELLS."""
    x0, y0, x1, y1 = bounds
    mid_lat = (y0 + y1) / 2
    deg_size = _degrees_for_cell_size(mid_lat)

    estimated_cells = int(((x1 - x0) / deg_size) * ((y1 - y0) / deg_size))
    if estimated_cells > MAX_SYNC_CELLS:
        raise AOITooLargeError(estimated_cells)

    with get_session() as session:
        session.execute(_MATERIALIZE_SQL, {"deg_size": deg_size, "x0": x0, "y0": y0, "x1": x1, "y1": y1, "cell_size_m": settings.grid_cell_size_m})
        rows = session.execute(_SELECT_CELLS_SQL, {"x0": x0, "y0": y0, "x1": x1, "y1": y1}).mappings().all()
    return [dict(r) for r in rows]
