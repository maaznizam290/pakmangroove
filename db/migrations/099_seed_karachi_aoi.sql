-- Seeds a default AOI so the app has something to render on first load.
-- This is an APPROXIMATE bounding box around the Karachi coastal mangrove
-- belt (Korangi/Phitti Creek, Bundal/Buddo Island, western Indus Delta
-- fringe) for use as the default map viewport — it is NOT an authoritative
-- mangrove or administrative boundary. Once GMW v4 vectors are ingested
-- (gmw_baseline_vectors), the real mangrove extent polygons should be used
-- for anything requiring boundary accuracy; this AOI only bounds the
-- default query/render window and is user-redrawable in the frontend.

INSERT INTO aois (name, geom, is_default, description) VALUES (
    'Karachi Coastal Mangroves (default, approximate)',
    ST_Multi(ST_GeomFromText(
        'POLYGON((66.85 24.65, 67.45 24.65, 67.45 24.95, 66.85 24.95, 66.85 24.65))',
        4326
    )),
    true,
    'Approximate default bounding box covering the Karachi coast, Korangi/Phitti Creek, and Bundal/Buddo Island area. Not an authoritative boundary — refine against ingested GMW v4 vectors.'
);
