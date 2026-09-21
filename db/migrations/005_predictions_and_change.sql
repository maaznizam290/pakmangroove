-- Model outputs: mangrove probability, health/canopy-condition indicator,
-- and change classification per cell. Every row is tagged OBSERVED,
-- DERIVED, or MODELLED so the API/frontend never blurs a satellite
-- observation into a model prediction.

CREATE TABLE mangrove_probability_cells (
    id              BIGSERIAL PRIMARY KEY,
    cell_id         BIGINT NOT NULL REFERENCES grid_cells(cell_id),
    composite_id    UUID NOT NULL REFERENCES sentinel2_composites(composite_id),
    model_id        UUID NOT NULL REFERENCES models(model_id),
    probability     DOUBLE PRECISION NOT NULL CHECK (probability BETWEEN 0 AND 1),
    predicted_class TEXT NOT NULL CHECK (predicted_class IN ('mangrove', 'non_mangrove')),
    result_type     TEXT NOT NULL DEFAULT 'MODELLED' CHECK (result_type = 'MODELLED'),
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cell_id, composite_id, model_id)
);
CREATE INDEX idx_mangrove_prob_cell ON mangrove_probability_cells (cell_id);

-- "REMOTE-SENSING VEGETATION / CANOPY CONDITION INDICATOR" — never labeled
-- "ecosystem health" per the build instructions.
CREATE TABLE canopy_condition_cells (
    id              BIGSERIAL PRIMARY KEY,
    cell_id         BIGINT NOT NULL REFERENCES grid_cells(cell_id),
    composite_id    UUID NOT NULL REFERENCES sentinel2_composites(composite_id),
    condition_indicator DOUBLE PRECISION NOT NULL,   -- composite of NDVI/EVI/NDMI etc., see mangrove_ai.health
    contributing_indices JSONB NOT NULL,             -- {"NDVI": 0.61, "EVI": 0.44, "NDMI": 0.31, ...}
    stress_flag     BOOLEAN NOT NULL DEFAULT false,
    result_type     TEXT NOT NULL DEFAULT 'DERIVED' CHECK (result_type = 'DERIVED'),
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cell_id, composite_id)
);
CREATE INDEX idx_canopy_condition_cell ON canopy_condition_cells (cell_id);

CREATE TABLE change_cells (
    id              BIGSERIAL PRIMARY KEY,
    cell_id         BIGINT NOT NULL REFERENCES grid_cells(cell_id),
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    change_class    TEXT NOT NULL CHECK (change_class IN ('gain', 'loss', 'stable', 'degraded_stressed')),
    change_rate_km2_per_yr DOUBLE PRECISION,
    fragmentation_index DOUBLE PRECISION,          -- e.g. edge density or patch-cohesion metric, null if not spatially supported
    sources         TEXT[] NOT NULL,               -- e.g. {'zenodo-...', 'gmw', 'cgmd-extent30', 'sentinel2'}
    result_type     TEXT NOT NULL CHECK (result_type IN ('OBSERVED', 'DERIVED', 'MODELLED')),
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_change_cells_cell_period ON change_cells (cell_id, period_start, period_end);

-- Forecast outputs, always labeled MODEL PREDICTION at the API layer.
-- Chronological split only — no random shuffle (enforced in training code,
-- documented here so the constraint travels with the schema).
CREATE TABLE forecast_runs (
    forecast_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aoi_id          UUID NOT NULL REFERENCES aois(aoi_id),
    model_id        UUID NOT NULL REFERENCES models(model_id),
    horizon_year    INTEGER NOT NULL,
    predicted_extent_km2 DOUBLE PRECISION NOT NULL,
    metrics         JSONB NOT NULL,                -- {"mae": ..., "rmse": ..., "mape": ...}
    baseline_comparison JSONB,                     -- {"naive_mae": ..., "linear_mae": ...} required before any GRU/LSTM row is promoted
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE forecast_runs IS
  'baseline_comparison must be populated (naive + linear baselines) before a GRU/LSTM forecast_runs row is written, per build instructions: establish simple baselines first.';
