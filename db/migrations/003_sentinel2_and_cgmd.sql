-- Sentinel-2 composite bookkeeping (rasters themselves stay in Earth
-- Engine / cloud storage — this table only records what was computed) and
-- CGMD-Extent30 / CGMD-AFCC30 annual per-cell time series (the cache layer
-- that makes chart serving instant; see docs/architecture/PAKMANG_AI_MVP_ENGINEERING_SPEC.md §3.1).

CREATE TABLE sentinel2_composites (
    composite_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aoi_id          UUID REFERENCES aois(aoi_id),
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    composite_type  TEXT NOT NULL CHECK (composite_type IN ('annual', 'seasonal', 'monthly')),
    cloud_prob_max  DOUBLE PRECISION NOT NULL DEFAULT 40,  -- COPERNICUS/S2_CLOUD_PROBABILITY threshold used
    ee_collection   TEXT NOT NULL DEFAULT 'COPERNICUS/S2_SR_HARMONIZED',
    scene_count     INTEGER,
    storage_ref     TEXT,                        -- Earth Engine asset id or export path of the composite, if exported
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_s2_composites_aoi_period ON sentinel2_composites (aoi_id, period_start, period_end);

-- Per-cell spectral index values for a given composite. One row per
-- (cell, composite, index) — sparse/tall rather than wide so adding a new
-- index never requires a migration.
CREATE TABLE spectral_index_values (
    id              BIGSERIAL PRIMARY KEY,
    cell_id         BIGINT NOT NULL REFERENCES grid_cells(cell_id),
    composite_id    UUID NOT NULL REFERENCES sentinel2_composites(composite_id),
    index_name      TEXT NOT NULL CHECK (index_name IN ('NDVI','EVI','MSAVI','NDWI','MNDWI','NDMI','MVI','SI','BSI')),
    value           DOUBLE PRECISION NOT NULL,
    UNIQUE (cell_id, composite_id, index_name)
);
CREATE INDEX idx_spectral_cell_composite ON spectral_index_values (cell_id, composite_id);
CREATE INDEX idx_spectral_index_name ON spectral_index_values (index_name);

-- CGMD-Extent30: annual mangrove extent per cell, 1984-2023.
CREATE TABLE cgmd_extent_annual (
    id              BIGSERIAL PRIMARY KEY,
    cell_id         BIGINT NOT NULL REFERENCES grid_cells(cell_id),
    year            INTEGER NOT NULL CHECK (year BETWEEN 1984 AND 2023),
    is_mangrove     BOOLEAN NOT NULL,
    source_asset    TEXT NOT NULL DEFAULT 'projects/mangrovedatahub2_assets/CGMD-Extent30SO',
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cell_id, year)
);
CREATE INDEX idx_cgmd_extent_cell_year ON cgmd_extent_annual (cell_id, year);

-- CGMD-AFCC30: annual fractional canopy cover per cell, 1984-2023.
-- source_asset is deliberately NOT hardcoded to a specific asset id here —
-- the build instructions flag that "CGMD-AFCC305" must not be assumed to
-- exist; the real Earth Engine asset id is supplied via configuration
-- (apps/api/mangrove_ai/config.py: CGMD_AFCC_ASSET_ID) and recorded per row.
CREATE TABLE cgmd_afcc_annual (
    id              BIGSERIAL PRIMARY KEY,
    cell_id         BIGINT NOT NULL REFERENCES grid_cells(cell_id),
    year            INTEGER NOT NULL CHECK (year BETWEEN 1984 AND 2023),
    fractional_cover DOUBLE PRECISION NOT NULL CHECK (fractional_cover BETWEEN 0 AND 1),
    source_asset    TEXT NOT NULL,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cell_id, year)
);
CREATE INDEX idx_cgmd_afcc_cell_year ON cgmd_afcc_annual (cell_id, year);

-- Pre-aggregated AOI-level annual gain/loss (km²) — the Chart-1 cache the
-- FastAPI /mangrove/extent-timeseries endpoint reads directly.
CREATE TABLE extent_timeseries_cache (
    id              BIGSERIAL PRIMARY KEY,
    aoi_id          UUID NOT NULL REFERENCES aois(aoi_id),
    year            INTEGER NOT NULL CHECK (year BETWEEN 1984 AND 2023),
    gain_km2        DOUBLE PRECISION NOT NULL DEFAULT 0,
    loss_km2        DOUBLE PRECISION NOT NULL DEFAULT 0,
    net_km2         DOUBLE PRECISION NOT NULL,
    total_extent_km2 DOUBLE PRECISION NOT NULL,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (aoi_id, year)
);
