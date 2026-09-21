"""Exercises a representative subset of the 15 MCP tools against the real
DB. With no Sentinel-2/CGMD/GMW/RAG data ingested for the test AOI, every
tool must report that honestly via `limitations` rather than fabricating
data — that contract is what's actually under test here."""

from mangrove_ai import tools
from mangrove_ai.schemas import ToolResponse


def test_query_sentinel_without_gee_credentials_reports_not_configured(small_bbox):
    result = tools.query_sentinel(bbox=small_bbox)
    assert isinstance(result, ToolResponse)
    assert result.data is None
    assert any("GEE" in lim or "credentials" in lim for lim in result.limitations)


def test_get_mangrove_timeseries_empty_is_honest_not_fabricated(small_bbox):
    result = tools.get_mangrove_timeseries(bbox=small_bbox)
    assert result.data == []
    assert result.limitations


def test_query_gmw_empty_is_honest(small_bbox):
    result = tools.query_gmw(bbox=small_bbox)
    assert result.data == []
    assert result.limitations


def test_calculate_restoration_suitability_returns_a_cell_per_grid_cell(small_bbox, small_cells):
    result = tools.calculate_restoration_suitability(bbox=small_bbox)
    assert result.data["cells"]
    assert len(result.data["cells"]) == len(small_cells)
    for cell in result.data["cells"]:
        assert cell["classification"] in ("VERY_HIGH", "HIGH", "MEDIUM", "LOW", "EXCLUDED")
        assert cell["field_validation_label"] == "Candidate restoration area — field validation required."
    assert result.model_version is not None


def test_calculate_restoration_suitability_refuses_oversized_aoi():
    huge_bbox = (66.85, 24.65, 67.45, 24.95)
    result = tools.calculate_restoration_suitability(bbox=huge_bbox)
    assert result.data["cells"] == []
    assert any("too large" in lim.lower() or "cells at" in lim for lim in result.limitations)


def test_search_ragflow_with_empty_corpus_is_insufficient_evidence():
    result = tools.search_ragflow("mangrove restoration Karachi heavy metals")
    assert result.data == []
    assert result.limitations


def test_generate_report_assembles_all_five_sections(small_bbox):
    result = tools.generate_report(bbox=small_bbox, question="Show me where mangrove restoration may be suitable and explain why.")
    for key in ("observed_data", "derived_analysis", "scientific_evidence", "model_output", "limitations"):
        assert key in result.data


def test_get_model_metadata_empty_registry_is_honest():
    result = tools.get_model_metadata(task="mangrove_classifier")
    assert result.data == []
    assert result.limitations
