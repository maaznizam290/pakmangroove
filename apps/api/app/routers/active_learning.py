from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mangrove_ai import active_learning

router = APIRouter(prefix="/active-learning", tags=["active-learning"])


@router.get("/review-queue")
def list_review_queue(status: str = "pending"):
    return active_learning.list_review_queue(status)


class ValidateReviewRequest(BaseModel):
    label_class: str
    validated_by: str


@router.post("/review-queue/{review_id}/validate")
def validate_review(review_id: str, body: ValidateReviewRequest):
    try:
        active_learning.validate_review(review_id, body.label_class, body.validated_by)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"status": "validated"}


class PromoteRequest(BaseModel):
    promoted_by: str
    reason: str


@router.post("/models/{model_id}/promote")
def promote_model(model_id: str, body: PromoteRequest):
    try:
        active_learning.promote_model(model_id, body.promoted_by, body.reason)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"status": "promoted"}
