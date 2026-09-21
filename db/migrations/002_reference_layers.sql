-- Slow-changing reference/validation vector layers: Global Mangrove Watch
-- baseline extent and the Zenodo Pakistan historical change layers.
-- Bulk-loaded by scheduled ETL, never written to by the live API.

CREATE TABLE gmw_baseline_vectors (
    id              BIGSERIAL PRIMARY KEY,
    gmw_feature_id  TEXT NOT NULL,
    source_version  TEXT NOT NULL,              -- e.g. 'GMW_v4_2023' — set at ingestion, not assumed
    geom            GEOMETRY(MultiPolygon, 4326) NOT NULL,
    area_km2        DOUBLE PRECISION,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_gmw_geom ON gmw_baseline_vectors USING GIST (geom);

CREATE TABLE zenodo_change_layers (
    id              BIGSERIAL PRIMARY KEY,
    zenodo_doi      TEXT NOT NULL DEFAULT '10.5281/zenodo.10732690',
    dataset_name    TEXT NOT NULL,               -- 'Indus Delta' | 'Sandspit' | 'MangroveSitesShapefile' | other
    change_class    TEXT NOT NULL CHECK (change_class IN ('gain', 'loss', 'stable', 'presence')),
    period_start    DATE,
    period_end      DATE,
    geom            GEOMETRY(MultiPolygon, 4326) NOT NULL,
    resolution_m    DOUBLE PRECISION NOT NULL DEFAULT 30,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_zenodo_geom ON zenodo_change_layers USING GIST (geom);
CREATE INDEX idx_zenodo_dataset ON zenodo_change_layers (dataset_name);

-- GBIF species occurrence records (secondary/context layer).
CREATE TABLE gbif_observations (
    occurrence_id   TEXT PRIMARY KEY,
    species         TEXT NOT NULL,
    geom            GEOMETRY(Point, 4326) NOT NULL,
    event_date      DATE,
    basis_of_record TEXT,
    source          TEXT NOT NULL DEFAULT 'GBIF',
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_gbif_geom ON gbif_observations USING GIST (geom);
CREATE INDEX idx_gbif_species ON gbif_observations (species);

-- Optional spatial context/constraint layers (Kaggle Pakistan admin/rivers/
-- roads, or any other exclusion-relevant vector data). Schema is generic —
-- layer_type distinguishes what each row represents.
CREATE TABLE spatial_context_layers (
    id              BIGSERIAL PRIMARY KEY,
    layer_type      TEXT NOT NULL CHECK (layer_type IN ('admin_boundary', 'river', 'road', 'built_up', 'other')),
    source          TEXT NOT NULL,               -- manifest id from data/knowledge_base/SOURCES_MANIFEST.yaml
    name            TEXT,
    geom            GEOMETRY(Geometry, 4326) NOT NULL,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_spatial_context_geom ON spatial_context_layers USING GIST (geom);
CREATE INDEX idx_spatial_context_type ON spatial_context_layers (layer_type);
