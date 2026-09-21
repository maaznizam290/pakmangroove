-- Restoration Suitability — the central intelligence feature. One
-- suitability_runs row per Hermes/API invocation; one suitability_cells
-- row per grid cell in that run's AOI. Every field required by the build
-- spec is a real column, not something bolted on client-side.

CREATE TABLE suitability_runs (
    run_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aoi_id          UUID NOT NULL REFERENCES aois(aoi_id),
    model_id        UUID NOT NULL REFERENCES models(model_id),
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    hermes_query_id UUID,                          -- links back to the Hermes orchestrator run that requested this, if any
    input_composite_id UUID REFERENCES sentinel2_composites(composite_id),
    feature_set     JSONB NOT NULL                 -- which of the ~20 candidate features were actually available/used for this run
);

CREATE TABLE suitability_cells (
    id              BIGSERIAL PRIMARY KEY,
    run_id          UUID NOT NULL REFERENCES suitability_runs(run_id),
    cell_id         BIGINT NOT NULL REFERENCES grid_cells(cell_id),
    suitability_score DOUBLE PRECISION NOT NULL CHECK (suitability_score BETWEEN 0 AND 1),
    confidence      DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    classification  TEXT NOT NULL CHECK (classification IN ('VERY_HIGH', 'HIGH', 'MEDIUM', 'LOW', 'EXCLUDED')),
    reason_codes    TEXT[] NOT NULL,                -- e.g. {'HISTORICAL_MANGROVE','INTERTIDAL_PROXIMITY','NEAR_EXISTING_MANGROVE'}
    data_sources    TEXT[] NOT NULL,                -- manifest ids / dataset names actually contributing to this cell's score
    model_version   TEXT NOT NULL,
    local_ecological_risk_evidence BOOLEAN NOT NULL DEFAULT false,
    field_validation_label TEXT NOT NULL DEFAULT 'Candidate restoration area — field validation required.',
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, cell_id)
);
CREATE INDEX idx_suitability_cells_run ON suitability_cells (run_id);
CREATE INDEX idx_suitability_cells_class ON suitability_cells (classification);

-- Enforce the labeling rule at the database layer, not just in application
-- code: any HIGH/VERY_HIGH row must carry the field-validation label.
ALTER TABLE suitability_cells ADD CONSTRAINT chk_field_validation_label
  CHECK (
    classification NOT IN ('HIGH', 'VERY_HIGH')
    OR field_validation_label = 'Candidate restoration area — field validation required.'
  );

-- Bundal Island (and any future local study) sampled heavy-metal points.
-- Point geometries only — this table is never rasterized/interpolated
-- into a continuous surface. See mangrove_ai.suitability.risk_evidence.
CREATE TABLE ecological_risk_samples (
    sample_id       BIGSERIAL PRIMARY KEY,
    study_source    TEXT NOT NULL DEFAULT 'bundal-island-ecotoxicology',  -- manifest id
    geom            GEOMETRY(Point, 4326) NOT NULL,
    sample_label    TEXT,                          -- the study's own site/station name
    metal           TEXT CHECK (metal IN ('Fe', 'Cr', 'Mn', 'Zn', 'Pb')),
    igeo            DOUBLE PRECISION,
    bcf             DOUBLE PRECISION,
    tf              DOUBLE PRECISION,
    species         TEXT DEFAULT 'Avicennia marina',
    source_page     INTEGER,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_ecological_risk_geom ON ecological_risk_samples USING GIST (geom);

COMMENT ON TABLE ecological_risk_samples IS
  'Point-only sampled evidence. A suitability cell within PROXIMITY_THRESHOLD_M (see mangrove_ai.config) of any row here gets local_ecological_risk_evidence=true; there is no citywide interpolation and no continuous pollution raster anywhere in this schema.';
