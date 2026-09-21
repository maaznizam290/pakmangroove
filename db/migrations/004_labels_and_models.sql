-- Training labels (spatially split, weak/coarse label documented) and the
-- model registry that backs get_model_metadata / active-learning promotion.

CREATE TABLE training_labels (
    label_id        BIGSERIAL PRIMARY KEY,
    geom            GEOMETRY(Geometry, 4326) NOT NULL,   -- point or polygon depending on source
    label_class     TEXT NOT NULL CHECK (label_class IN ('mangrove', 'non_mangrove', 'degraded_mangrove', 'water', 'built_up', 'other')),
    source          TEXT NOT NULL,               -- manifest id, e.g. 'zenodo-10.5281-zenodo.10732690' or 'gmw'
    source_resolution_m DOUBLE PRECISION,
    is_weak_label   BOOLEAN NOT NULL DEFAULT true,  -- true unless the source is independently confirmed pixel-accurate at the target resolution
    spatial_split   TEXT NOT NULL CHECK (spatial_split IN ('train', 'val', 'test')),
    split_region    TEXT,                         -- name of the spatially-separated region this label falls in, to make leakage auditable
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_training_labels_geom ON training_labels USING GIST (geom);
CREATE INDEX idx_training_labels_split ON training_labels (spatial_split);

COMMENT ON COLUMN training_labels.is_weak_label IS
  'Per build instructions: 30m CGMD/Zenodo labels are never treated as automatically-correct 10m Sentinel-2 labels. Default true; set false only with an explicit, documented justification.';

CREATE TABLE models (
    model_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task            TEXT NOT NULL CHECK (task IN ('mangrove_classifier', 'health_indicator', 'restoration_suitability', 'temporal_forecast')),
    version         TEXT NOT NULL,                -- semver-ish, e.g. 'rf-v0.1.0'
    algorithm       TEXT NOT NULL,                -- 'RandomForest' | 'GradientBoosting' | 'UNet++' | 'NaiveBaseline' | 'LinearRegression' | 'GRU' | 'LSTM'
    training_data_ref TEXT,                       -- description/query of the training_labels slice used
    metrics         JSONB NOT NULL DEFAULT '{}',  -- precision/recall/f1/iou/miou/confusion_matrix or mae/rmse/mape
    feature_importance JSONB,
    hyperparameters JSONB,
    promoted        BOOLEAN NOT NULL DEFAULT false,
    promoted_at     TIMESTAMPTZ,
    promoted_reason TEXT,
    trained_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      TEXT NOT NULL DEFAULT 'system',  -- 'system' | 'hermes_retrain_job' | a human identifier on manual promotion
    UNIQUE (task, version)
);
CREATE INDEX idx_models_task_promoted ON models (task, promoted);

COMMENT ON TABLE models IS
  'Promotion is a human-gated write (promoted_reason required, see mangrove_ai.active_learning.promote) — Hermes/the retrain job may create a new candidate row but never flips promoted=true itself.';

-- Active-learning review queue: low-confidence / high-change tiles queued
-- for human validation before their predictions can inform retraining.
CREATE TABLE review_queue (
    review_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cell_id         BIGINT NOT NULL REFERENCES grid_cells(cell_id),
    reason          TEXT NOT NULL CHECK (reason IN ('low_confidence', 'high_change', 'model_disagreement')),
    model_id        UUID REFERENCES models(model_id),
    confidence      DOUBLE PRECISION,
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'validated', 'rejected')),
    assigned_to     TEXT,
    validated_label_id BIGINT REFERENCES training_labels(label_id),
    validated_by    TEXT,
    validated_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_review_queue_status ON review_queue (status);
