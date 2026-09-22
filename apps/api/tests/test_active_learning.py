import pytest
from sqlalchemy import text

from mangrove_ai import active_learning as al
from mangrove_ai.db import get_session

TEST_TASK = "mangrove_classifier"
TEST_VERSION_PREFIX = "test-fixture-"


@pytest.fixture()
def cleanup_test_models():
    yield
    with get_session() as session:
        session.execute(text("DELETE FROM models WHERE version LIKE :p"), {"p": f"{TEST_VERSION_PREFIX}%"})


def test_queue_and_validate_review_writes_a_real_training_label(small_cells):
    cell_id = small_cells[0]["cell_id"]
    review_id = al.queue_for_review(cell_id, "low_confidence", confidence=0.2)

    pending = al.list_review_queue("pending")
    assert any(r["review_id"] == review_id for r in pending)

    al.validate_review(review_id, "mangrove", validated_by="reviewer@example.com")

    still_pending = al.list_review_queue("pending")
    assert not any(r["review_id"] == review_id for r in still_pending)

    with get_session() as session:
        row = session.execute(
            text("SELECT label_class, source, is_weak_label, validated_label_id FROM training_labels tl "
                 "JOIN review_queue rq ON rq.validated_label_id = tl.label_id WHERE rq.review_id = :id"),
            {"id": review_id},
        ).mappings().first()
        label_id = row["validated_label_id"]
        session.execute(text("DELETE FROM review_queue WHERE review_id = :id"), {"id": review_id})
        session.execute(text("DELETE FROM training_labels WHERE label_id = :label_id"), {"label_id": label_id})
    assert row["label_class"] == "mangrove"
    assert row["source"] == "active_learning_review"


def test_queue_rejects_invalid_reason(small_cells):
    with pytest.raises(ValueError):
        al.queue_for_review(small_cells[0]["cell_id"], "because_i_felt_like_it")


def test_promote_refuses_system_or_hermes_as_promoter(cleanup_test_models):
    model_id = al.register_candidate_model(TEST_TASK, f"{TEST_VERSION_PREFIX}v1", "RandomForest", {"f1": 0.7}, None, "real_training_labels_slice", is_synthetic=False)
    with pytest.raises(PermissionError):
        al.promote_model(model_id, "system", "should not be allowed")
    with pytest.raises(PermissionError):
        al.promote_model(model_id, "hermes_retrain_job", "should not be allowed")


def test_promote_succeeds_with_real_human_identifier(cleanup_test_models):
    model_id = al.register_candidate_model(TEST_TASK, f"{TEST_VERSION_PREFIX}v2", "RandomForest", {"f1": 0.7}, None, "real_training_labels_slice", is_synthetic=False)
    al.promote_model(model_id, "a.human.reviewer@example.com", "first model for this task")

    with get_session() as session:
        promoted = session.execute(text("SELECT promoted FROM models WHERE model_id = :id"), {"id": model_id}).scalar()
    assert promoted is True


def test_promote_refuses_to_demote_a_better_model(cleanup_test_models):
    better = al.register_candidate_model(TEST_TASK, f"{TEST_VERSION_PREFIX}better", "RandomForest", {"f1": 0.9}, None, "real_training_labels_slice", is_synthetic=False)
    al.promote_model(better, "a.human@example.com", "initial promotion")

    worse = al.register_candidate_model(TEST_TASK, f"{TEST_VERSION_PREFIX}worse", "RandomForest", {"f1": 0.5}, None, "real_training_labels_slice", is_synthetic=False)
    with pytest.raises(ValueError):
        al.promote_model(worse, "a.human@example.com", "attempt to regress")

    with get_session() as session:
        still_promoted = session.execute(text("SELECT model_id FROM models WHERE task = :t AND promoted = true"), {"t": TEST_TASK}).scalar()
    assert str(still_promoted) == better


def test_promote_refuses_a_synthetic_candidate_regardless_of_promoter(cleanup_test_models):
    model_id = al.register_candidate_model(
        TEST_TASK, f"{TEST_VERSION_PREFIX}synthetic", "RandomForest", {"f1": 1.0}, None,
        "mangrove_ai.fixtures.synthetic_band_pixels (SMOKE TEST)", is_synthetic=True,
    )
    with pytest.raises(PermissionError, match="synthetic"):
        al.promote_model(model_id, "a.human.reviewer@example.com", "should never be allowed")

    with get_session() as session:
        promoted = session.execute(text("SELECT promoted FROM models WHERE model_id = :id"), {"id": model_id}).scalar()
    assert promoted is False
