"""Tool specs shared by the MCP server (mangrove_ai/mcp_server.py) and the
LLM-driven Hermes planner (mangrove_ai/hermes/orchestrator.py) — one
definition, two callers, so the tool surface Hermes can reach is always
exactly the set of real functions in mangrove_ai.tools (plus the
review-queue write, never model promotion — see mangrove_ai.active_learning).
"""

from __future__ import annotations

from mangrove_ai import tools as _tools
from mangrove_ai.active_learning import queue_for_review

_AOI_PROPS = {
    "aoi_id": {"type": "string", "description": "An existing AOI's UUID. Omit if using bbox."},
    "bbox": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4,
              "description": "[minLon, minLat, maxLon, maxLat]. Omit to use the default Karachi AOI."},
}

TOOL_SPECS: list[dict] = [
    {"name": "query_sentinel", "description": "Filter/cloud-mask/composite Sentinel-2 SR imagery for an AOI and period.",
     "input_schema": {"type": "object", "properties": {**_AOI_PROPS, "period_start": {"type": "string"}, "period_end": {"type": "string"}, "composite_type": {"type": "string", "enum": ["annual", "seasonal", "monthly"]}}}},
    {"name": "get_map_layer", "description": "Real GEE-hosted XYZ tile URL for a Sentinel-2 composite visualization (true_color | false_color | ndvi | ndwi | mndwi) for an AOI/period, ready to add to a map.",
     "input_schema": {"type": "object", "properties": {**_AOI_PROPS, "period_start": {"type": "string"}, "period_end": {"type": "string"}, "composite_type": {"type": "string", "enum": ["annual", "seasonal", "monthly"]}, "layer": {"type": "string", "enum": ["true_color", "false_color", "ndvi", "ndwi", "mndwi"]}}}},
    {"name": "get_mangrove_map", "description": "Per-cell current mangrove probability/classification for an AOI/year.",
     "input_schema": {"type": "object", "properties": {**_AOI_PROPS, "year": {"type": "integer"}}}},
    {"name": "get_mangrove_timeseries", "description": "Annual mangrove extent gain/loss/net time series (CGMD-Extent30) for an AOI.",
     "input_schema": {"type": "object", "properties": _AOI_PROPS}},
    {"name": "query_gmw", "description": "Global Mangrove Watch v4 baseline extent vectors intersecting an AOI.",
     "input_schema": {"type": "object", "properties": _AOI_PROPS}},
    {"name": "query_gbif", "description": "GBIF species occurrence records within an AOI.",
     "input_schema": {"type": "object", "properties": {**_AOI_PROPS, "species": {"type": "string"}}}},
    {"name": "query_cgmd", "description": "CGMD-Extent30 and CGMD-AFCC30 annual per-cell values for an AOI/year.",
     "input_schema": {"type": "object", "properties": {**_AOI_PROPS, "year": {"type": "integer"}}}},
    {"name": "calculate_change", "description": "Gain/loss/stable/degraded_stressed classification and change rate for an AOI/period.",
     "input_schema": {"type": "object", "properties": {**_AOI_PROPS, "period_start": {"type": "integer"}, "period_end": {"type": "integer"}}}},
    {"name": "calculate_health_indicators", "description": "Remote-sensing vegetation/canopy condition indicator per cell for an AOI/year.",
     "input_schema": {"type": "object", "properties": {**_AOI_PROPS, "year": {"type": "integer"}}}},
    {"name": "calculate_restoration_suitability", "description": "The central tool: per-cell restoration suitability score, confidence, reason codes, classification, and field-validation label for an AOI.",
     "input_schema": {"type": "object", "properties": _AOI_PROPS}},
    {"name": "run_forecast", "description": "Naive/linear (and, once justified, GRU/LSTM) extent forecast for an AOI, chronologically split, always labeled MODEL PREDICTION.",
     "input_schema": {"type": "object", "properties": {**_AOI_PROPS, "horizon_year": {"type": "integer"}, "model_type": {"type": "string", "enum": ["naive", "linear", "gru", "lstm"]}}}},
    {"name": "search_ragflow", "description": "Query the scientific/context RAG knowledge base (Mangrove_AI_Knowledge). Returns cited passages or an explicit insufficient-evidence result.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "location": {"type": "string"}, "category": {"type": "string"}, "top_k": {"type": "integer"}}, "required": ["query"]}},
    {"name": "generate_map", "description": "Structured GeoJSON-ready payload for a named map layer (mangrove_extent | gmw_baseline | gbif | cgmd | restoration_suitability).",
     "input_schema": {"type": "object", "properties": {"layer": {"type": "string"}, **_AOI_PROPS}, "required": ["layer"]}},
    {"name": "generate_chart", "description": "Chart-ready data for a named chart_type (extent_timeseries | health_indicators).",
     "input_schema": {"type": "object", "properties": {"chart_type": {"type": "string"}, **_AOI_PROPS}, "required": ["chart_type"]}},
    {"name": "generate_report", "description": "Assembles the OBSERVED / DERIVED / SCIENTIFIC EVIDENCE / MODEL OUTPUT / LIMITATIONS answer envelope for a question about an AOI from the other tools.",
     "input_schema": {"type": "object", "properties": {**_AOI_PROPS, "question": {"type": "string"}}}},
    {"name": "get_model_metadata", "description": "Registered model versions, metrics, and promotion status for a task.",
     "input_schema": {"type": "object", "properties": {"task": {"type": "string"}, "version": {"type": "string"}}}},
    {"name": "queue_for_review", "description": "Queue a low-confidence or high-change cell for human validation (active learning). Never promotes a model.",
     "input_schema": {"type": "object", "properties": {"cell_id": {"type": "integer"}, "reason": {"type": "string", "enum": ["low_confidence", "high_change", "model_disagreement"]}, "confidence": {"type": "number"}}, "required": ["cell_id", "reason"]}},
]


def _bbox_tuple(args: dict) -> tuple | None:
    return tuple(args["bbox"]) if args.get("bbox") else None


TOOL_DISPATCH = {
    "query_sentinel": lambda a: _tools.query_sentinel(a.get("aoi_id"), _bbox_tuple(a), a.get("period_start"), a.get("period_end"), a.get("composite_type", "annual")),
    "get_map_layer": lambda a: _tools.get_map_layer(a.get("aoi_id"), _bbox_tuple(a), a.get("period_start"), a.get("period_end"), a.get("composite_type", "annual"), a.get("layer", "true_color")),
    "get_mangrove_map": lambda a: _tools.get_mangrove_map(a.get("aoi_id"), _bbox_tuple(a), a.get("year")),
    "get_mangrove_timeseries": lambda a: _tools.get_mangrove_timeseries(a.get("aoi_id"), _bbox_tuple(a)),
    "query_gmw": lambda a: _tools.query_gmw(a.get("aoi_id"), _bbox_tuple(a)),
    "query_gbif": lambda a: _tools.query_gbif(a.get("aoi_id"), _bbox_tuple(a), a.get("species")),
    "query_cgmd": lambda a: _tools.query_cgmd(a.get("aoi_id"), _bbox_tuple(a), a.get("year")),
    "calculate_change": lambda a: _tools.calculate_change(a.get("aoi_id"), _bbox_tuple(a), a.get("period_start"), a.get("period_end")),
    "calculate_health_indicators": lambda a: _tools.calculate_health_indicators(a.get("aoi_id"), _bbox_tuple(a), a.get("year")),
    "calculate_restoration_suitability": lambda a: _tools.calculate_restoration_suitability(a.get("aoi_id"), _bbox_tuple(a)),
    "run_forecast": lambda a: _tools.run_forecast(a.get("aoi_id"), _bbox_tuple(a), a.get("horizon_year", 2030), a.get("model_type", "naive")),
    "search_ragflow": lambda a: _tools.search_ragflow(a["query"], a.get("location"), a.get("category"), a.get("top_k", 5)),
    "generate_map": lambda a: _tools.generate_map(a["layer"], a.get("aoi_id"), _bbox_tuple(a)),
    "generate_chart": lambda a: _tools.generate_chart(a["chart_type"], a.get("aoi_id"), _bbox_tuple(a)),
    "generate_report": lambda a: _tools.generate_report(a.get("aoi_id"), _bbox_tuple(a), a.get("question")),
    "get_model_metadata": lambda a: _tools.get_model_metadata(a.get("task"), a.get("version")),
    "queue_for_review": lambda a: queue_for_review(a["cell_id"], a["reason"], confidence=a.get("confidence")),
}
