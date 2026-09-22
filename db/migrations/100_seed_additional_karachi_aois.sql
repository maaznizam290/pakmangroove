-- Adds the two remaining named AOIs the build spec calls for alongside the
-- default Bundal Island / Korangi Creek AOI (099): a Karachi coastal
-- mangrove site (Sandspit) and an Indus Delta site (Keti Bunder vicinity).
-- Same convention as 099: each box is an APPROXIMATE, coarse regional query
-- window centered on a well-known named place, NOT a surveyed mangrove or
-- administrative boundary, and deliberately kept small enough to stay under
-- MAX_SYNC_CELLS (10,000 cells at 30m) for synchronous grid materialization.
-- Replace with a validated boundary (e.g. once GMW v4 vectors are ingested)
-- before treating these as anything more precise than "roughly here."

INSERT INTO aois (name, geom, is_default, description) VALUES (
    'Sandspit (Karachi coastal mangroves, approximate)',
    ST_Multi(ST_GeomFromText(
        'POLYGON((66.920 24.825, 66.945 24.825, 66.945 24.845, 66.920 24.845, 66.920 24.825))',
        4326
    )),
    false,
    'Approximate ~2.3km x 2.2km query window over the Sandspit backwater mangrove area near Karachi harbour. Not an authoritative boundary — refine against ingested GMW v4 vectors. Draw a custom AOI in the frontend for a different extent.'
);

INSERT INTO aois (name, geom, is_default, description) VALUES (
    'Keti Bunder / Indus Delta (approximate)',
    ST_Multi(ST_GeomFromText(
        'POLYGON((67.430 24.140, 67.455 24.140, 67.455 24.160, 67.430 24.160, 67.430 24.140))',
        4326
    )),
    false,
    'Approximate ~2.3km x 2.2km query window near Keti Bunder in the Indus Delta mangrove belt. Not an authoritative boundary — refine against ingested GMW v4 vectors. Draw a custom AOI in the frontend for a different extent.'
);
