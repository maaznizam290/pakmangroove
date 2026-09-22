-- Structural guard against synthetic fixture metrics being mistaken for
-- (or promoted as) real model performance. register_candidate_model() in
-- mangrove_ai.active_learning now requires an explicit is_synthetic flag
-- on every insert, and promote_model() refuses to promote a synthetic row
-- regardless of its metrics.

ALTER TABLE models ADD COLUMN is_synthetic BOOLEAN NOT NULL DEFAULT false;

COMMENT ON COLUMN models.is_synthetic IS
  'true for rows trained on mangrove_ai.fixtures synthetic data (software smoke test only) — never a real, scientifically valid metric. Never promotable regardless of its metrics; see mangrove_ai.active_learning.promote_model.';
