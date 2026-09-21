"""Active learning / self-improvement loop — human-gated at every write
that matters. Hermes may call `queue_for_review` and `propose_retrain`; it
may never call `promote_model` itself (see PROMOTION_REQUIRES_HUMAN below
and the enforcement in app/routers/active_learning.py, which only exposes
promote() to an authenticated human-operator route, never to the Hermes
tool surface in mangrove_ai/mcp_server.py).
"""

from __future__ import annotations

from sqlalchemy import text

from mangrove_ai.db import get_session

PROMOTION_REQUIRES_HUMAN = True


def queue_for_review(cell_id: int, reason: str, model_id: str | None = None, confidence: float | None = None) -> str:
    if reason not in ("low_confidence", "high_change", "model_disagreement"):
        raise ValueError(f"invalid reason: {reason}")
    with get_session() as session:
        review_id = session.execute(
            text("""INSERT INTO review_queue (cell_id, reason, model_id, confidence)
                     VALUES (:cell_id, :reason, :model_id, :confidence) RETURNING review_id"""),
            {"cell_id": cell_id, "reason": reason, "model_id": model_id, "confidence": confidence},
        ).scalar()
    return str(review_id)


def list_review_queue(status: str = "pending") -> list[dict]:
    with get_session() as session:
        rows = session.execute(
            text("""SELECT r.review_id, r.cell_id, r.reason, r.confidence, r.status, r.created_at,
                            ST_X(g.centroid) AS lon, ST_Y(g.centroid) AS lat
                     FROM review_queue r JOIN grid_cells g ON g.cell_id = r.cell_id
                     WHERE r.status = :status ORDER BY r.created_at"""),
            {"status": status},
        ).mappings().all()
    return [{**dict(r), "review_id": str(r["review_id"])} for r in rows]


def validate_review(review_id: str, label_class: str, validated_by: str) -> None:
    """Human validation: writes a training_labels row and marks the review
    resolved. This is the only path new labeled data enters training_labels
    from the review queue — never an automatic write from a model's own
    prediction."""
    with get_session() as session:
        review = session.execute(text("SELECT cell_id FROM review_queue WHERE review_id = :id"), {"id": review_id}).mappings().first()
        if not review:
            raise ValueError(f"No review_queue row with id {review_id}")

        label_id = session.execute(
            text("""INSERT INTO training_labels (geom, label_class, source, is_weak_label, spatial_split, split_region)
                     SELECT geom, :label_class, 'active_learning_review', false, 'train', 'active_learning'
                     FROM grid_cells WHERE cell_id = :cell_id RETURNING label_id"""),
            {"label_class": label_class, "cell_id": review["cell_id"]},
        ).scalar()

        session.execute(
            text("""UPDATE review_queue SET status = 'validated', validated_label_id = :label_id,
                        validated_by = :validated_by, validated_at = now() WHERE review_id = :id"""),
            {"label_id": label_id, "validated_by": validated_by, "id": review_id},
        )


def register_candidate_model(task: str, version: str, algorithm: str, metrics: dict,
                              feature_importance: dict | None, training_data_ref: str,
                              created_by: str = "hermes_retrain_job") -> str:
    """Writes a new, unpromoted candidate row. This is what Hermes/a retrain
    job is allowed to do — promoted defaults to false."""
    with get_session() as session:
        model_id = session.execute(
            text("""INSERT INTO models (task, version, algorithm, training_data_ref, metrics, feature_importance, created_by)
                     VALUES (:task, :version, :algorithm, :training_data_ref, CAST(:metrics AS jsonb), CAST(:feature_importance AS jsonb), :created_by)
                     RETURNING model_id"""),
            {"task": task, "version": version, "algorithm": algorithm, "training_data_ref": training_data_ref,
             "metrics": __import__("json").dumps(metrics), "feature_importance": __import__("json").dumps(feature_importance or {}),
             "created_by": created_by},
        ).scalar()
    return str(model_id)


def promote_model(model_id: str, promoted_by: str, reason: str) -> None:
    """The only function that flips models.promoted = true. Requires an
    explicit human identifier and reason — never called by Hermes or the
    retrain job themselves (enforced by not exposing this in
    mangrove_ai/mcp_server.py's tool list)."""
    if not promoted_by or promoted_by in ("system", "hermes_retrain_job"):
        raise PermissionError("Model promotion requires a real human identifier in promoted_by.")

    with get_session() as session:
        candidate = session.execute(text("SELECT task, metrics FROM models WHERE model_id = :id"), {"id": model_id}).mappings().first()
        if not candidate:
            raise ValueError(f"No model {model_id}")

        current = session.execute(
            text("SELECT model_id, metrics FROM models WHERE task = :task AND promoted = true ORDER BY promoted_at DESC LIMIT 1"),
            {"task": candidate["task"]},
        ).mappings().first()

        if current is not None:
            new_key_metric = _primary_metric(candidate["metrics"])
            old_key_metric = _primary_metric(current["metrics"])
            if new_key_metric is not None and old_key_metric is not None and new_key_metric < old_key_metric:
                raise ValueError(
                    f"Candidate's primary metric ({new_key_metric}) does not improve on the currently promoted "
                    f"model's ({old_key_metric}) — promotion refused. Override only via an explicit human decision "
                    "documented in `reason`, by calling this function again with acceptance-criteria context."
                )
            session.execute(text("UPDATE models SET promoted = false WHERE model_id = :id"), {"id": current["model_id"]})

        session.execute(
            text("UPDATE models SET promoted = true, promoted_at = now(), promoted_reason = :reason WHERE model_id = :id"),
            {"reason": f"[{promoted_by}] {reason}", "id": model_id},
        )


def _primary_metric(metrics: dict) -> float | None:
    for key in ("f1", "miou", "mae"):
        if key in metrics:
            return -metrics[key] if key == "mae" else metrics[key]  # lower MAE is better -> negate for a uniform "higher is better" comparison
    return None
