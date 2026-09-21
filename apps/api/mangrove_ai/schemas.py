"""Shared response envelope. Every MCP tool / FastAPI endpoint that produces
an analytical result returns one of these — this is the single place the
"data / source / timestamp / parameters / model_version / confidence /
limitations" contract required by the build spec is enforced in code."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ToolResponse(BaseModel):
    data: Any
    source: list[str] = Field(description="Manifest ids / dataset names / EE collection ids this result is drawn from")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    parameters: dict[str, Any] = Field(default_factory=dict)
    model_version: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    limitations: list[str] = Field(default_factory=list)


class AnswerEnvelope(BaseModel):
    """The five-part answer structure every Hermes/RAG answer must separate."""

    observed_data: list[str] = Field(default_factory=list)
    derived_analysis: list[str] = Field(default_factory=list)
    scientific_evidence: list["Citation"] = Field(default_factory=list)
    model_output: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    doc_id: str
    title: str
    section: str | None = None
    page: int | None = None
    quote: str | None = None


class SuitabilityCellResult(BaseModel):
    cell_id: int
    lon: float
    lat: float
    suitability_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    classification: str  # VERY_HIGH | HIGH | MEDIUM | LOW | EXCLUDED
    reason_codes: list[str]
    data_sources: list[str]
    model_version: str
    local_ecological_risk_evidence: bool
    field_validation_label: str = "Candidate restoration area — field validation required."


AnswerEnvelope.model_rebuild()
