-- Seeds a default AOI so the app has something to render on first load.
-- This is an APPROXIMATE ~2.5km x 2.5km bounding box in the Karachi
-- coastal mangrove belt (Korangi Creek / Bundal Island vicinity) — it is
-- NOT an authoritative mangrove or administrative boundary. Once GMW v4
-- vectors are ingested (gmw_baseline_vectors), the real mangrove extent
-- polygons should be used for anything requiring boundary accuracy; this
-- AOI only bounds the default query/render window and is user-redrawable
-- in the frontend.
--
-- Deliberately kept small (~6,800 cells at 30m resolution): grid
-- materialization (mangrove_ai.geo.ensure_grid_cells) is synchronous and
-- capped at MAX_SYNC_CELLS=10,000 — the originally seeded full-coast
-- bounding box (66.85-67.45, 24.65-24.95) was ~2M cells and hung any
-- suitability/health/CGMD query against it. A larger AOI is still
-- explorable by drawing a custom bbox in the frontend; it will surface a
-- clear "AOI too large" limitation rather than hang.

INSERT INTO aois (name, geom, is_default, description) VALUES (
    'Bundal Island / Korangi Creek (default, approximate)',
    ST_Multi(ST_GeomFromText(
        'POLYGON((67.10 24.780, 67.1247 24.780, 67.1247 24.8025, 67.10 24.8025, 67.10 24.780))',
        4326
    )),
    true,
    'Approximate ~2.5km x 2.5km default bounding box in the Bundal Island / Korangi Creek vicinity of the Karachi coast, sized to stay under the synchronous grid-materialization cell cap. Not an authoritative boundary — refine against ingested GMW v4 vectors. Draw a custom AOI in the frontend to explore elsewhere.'
);
