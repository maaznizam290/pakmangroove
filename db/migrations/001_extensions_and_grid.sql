-- PakMang AI / Mangrove AI Intelligence — core extensions and the fixed
-- analysis grid that every raster-derived metric (extent, health,
-- suitability) is aggregated onto for fast, cacheable serving.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()

-- One row per analysis cell on a fixed grid over the Karachi/Bundal/Indus
-- Delta AOI. cell_size_m defaults to 30m to match CGMD-Extent30/AFCC30
-- native resolution; Sentinel-2-only metrics (10m bands/indices) are
-- aggregated up to this same grid so every layer joins cleanly.
CREATE TABLE grid_cells (
    cell_id         BIGSERIAL PRIMARY KEY,
    cell_key        TEXT NOT NULL UNIQUE,      -- deterministic key, e.g. 'S30-<snapped x>-<snapped y>'
    geom            GEOMETRY(Polygon, 4326) NOT NULL,
    centroid         GEOMETRY(Point, 4326) NOT NULL,
    cell_size_m     DOUBLE PRECISION NOT NULL DEFAULT 30,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_grid_cells_geom ON grid_cells USING GIST (geom);
CREATE INDEX idx_grid_cells_centroid ON grid_cells USING GIST (centroid);

-- Named AOIs (Karachi coast, Bundal Island, Indus Delta subareas, or a
-- user-drawn polygon) that requests and Hermes queries resolve against.
CREATE TABLE aois (
    aoi_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    geom            GEOMETRY(MultiPolygon, 4326) NOT NULL,
    is_default      BOOLEAN NOT NULL DEFAULT false,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_aois_geom ON aois USING GIST (geom);

COMMENT ON TABLE aois IS 'Karachi coastal mangrove default AOI plus Bundal/Indus Delta subareas and any user-drawn AOI; seeded in 099_seed_karachi_aoi.sql.';
