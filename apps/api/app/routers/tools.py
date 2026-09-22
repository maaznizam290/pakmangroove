"""REST endpoints mirroring the 15 MCP tools 1:1 — see mangrove_ai/tools.py
for the actual implementations. This router just parses query params and
returns the ToolResponse envelope as JSON."""

from __future__ import annotations

from fastapi import APIRouter, Query

from mangrove_ai import tools
from mangrove_ai.schemas import ToolResponse

router = APIRouter(tags=["tools"])


def _bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    if not bbox:
        return None
    parts = [float(p) for p in bbox.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must be 'minLon,minLat,maxLon,maxLat'")
    return tuple(parts)  # type: ignore[return-value]


@router.get("/mangrove/sentinel", response_model=ToolResponse)
def query_sentinel(aoi_id: str | None = None, bbox: str | None = Query(None),
                    period_start: str | None = None, period_end: str | None = None,
                    composite_type: str = "annual"):
    return tools.query_sentinel(aoi_id, _bbox(bbox), period_start, period_end, composite_type)


@router.get("/mangrove/map", response_model=ToolResponse)
def get_mangrove_map(aoi_id: str | None = None, bbox: str | None = Query(None), year: int | None = None):
    return tools.get_mangrove_map(aoi_id, _bbox(bbox), year)


@router.get("/mangrove/extent-timeseries", response_model=ToolResponse)
def get_mangrove_timeseries(aoi_id: str | None = None, bbox: str | None = Query(None)):
    return tools.get_mangrove_timeseries(aoi_id, _bbox(bbox))


@router.get("/mangrove/gmw", response_model=ToolResponse)
def query_gmw(aoi_id: str | None = None, bbox: str | None = Query(None)):
    return tools.query_gmw(aoi_id, _bbox(bbox))


@router.get("/mangrove/gbif", response_model=ToolResponse)
def query_gbif(aoi_id: str | None = None, bbox: str | None = Query(None), species: str | None = None):
    return tools.query_gbif(aoi_id, _bbox(bbox), species)


@router.get("/mangrove/cgmd", response_model=ToolResponse)
def query_cgmd(aoi_id: str | None = None, bbox: str | None = Query(None), year: int | None = None):
    return tools.query_cgmd(aoi_id, _bbox(bbox), year)


@router.get("/mangrove/change", response_model=ToolResponse)
def calculate_change(aoi_id: str | None = None, bbox: str | None = Query(None),
                      period_start: int | None = None, period_end: int | None = None):
    return tools.calculate_change(aoi_id, _bbox(bbox), period_start, period_end)


@router.get("/mangrove/health", response_model=ToolResponse)
def calculate_health_indicators(aoi_id: str | None = None, bbox: str | None = Query(None), year: int | None = None):
    return tools.calculate_health_indicators(aoi_id, _bbox(bbox), year)


@router.get("/mangrove/restoration-suitability", response_model=ToolResponse)
def calculate_restoration_suitability(aoi_id: str | None = None, bbox: str | None = Query(None)):
    return tools.calculate_restoration_suitability(aoi_id, _bbox(bbox))


@router.get("/mangrove/forecast", response_model=ToolResponse)
def run_forecast(aoi_id: str | None = None, bbox: str | None = Query(None),
                  horizon_year: int = 2030, model_type: str = "naive"):
    return tools.run_forecast(aoi_id, _bbox(bbox), horizon_year, model_type)


@router.get("/rag/search", response_model=ToolResponse)
def search_ragflow(query: str, location: str | None = None, category: str | None = None, top_k: int = 5):
    return tools.search_ragflow(query, location, category, top_k)


@router.get("/rag/sources")
def list_sources():
    from mangrove_ai.rag.sources import list_sources as _list_sources

    return _list_sources()


@router.get("/visualization/map", response_model=ToolResponse)
def generate_map(layer: str, aoi_id: str | None = None, bbox: str | None = Query(None)):
    return tools.generate_map(layer, aoi_id, _bbox(bbox))


@router.get("/visualization/chart", response_model=ToolResponse)
def generate_chart(chart_type: str, aoi_id: str | None = None, bbox: str | None = Query(None)):
    return tools.generate_chart(chart_type, aoi_id, _bbox(bbox))


@router.get("/report", response_model=ToolResponse)
def generate_report(aoi_id: str | None = None, bbox: str | None = Query(None), question: str | None = None):
    return tools.generate_report(aoi_id, _bbox(bbox), question)


@router.get("/models", response_model=ToolResponse)
def get_model_metadata(task: str | None = None, version: str | None = None):
    return tools.get_model_metadata(task, version)


@router.get("/aoi/default")
def get_default_aoi():
    from mangrove_ai.geo import resolve_aoi

    aoi = resolve_aoi()
    return {"aoi_id": aoi["aoi_id"], "bounds": aoi["bounds"]}


@router.get("/aoi/list")
def list_aois():
    from mangrove_ai.geo import list_aois as _list_aois

    return _list_aois()


@router.post("/hermes/ask", response_model=dict)
def hermes_ask(payload: dict):
    from mangrove_ai.hermes.orchestrator import run as hermes_run

    return hermes_run(payload["question"], aoi_id=payload.get("aoi_id"), bbox=payload.get("bbox"))
