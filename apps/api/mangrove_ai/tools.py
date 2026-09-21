"""The 15 MCP tool implementations. Each function returns a ToolResponse
(data/source/timestamp/parameters/model_version/confidence/limitations) —
this module is the single implementation both the FastAPI routers
(app/routers/tools.py) and the MCP server (mangrove_ai/mcp_server.py)
call, so there is exactly one place tool behavior lives.

Hermes calls these tools; it never computes a geospatial result itself
(see services/hermes/orchestrator.py).
"""

from __future__ import annotations

import numpy as np
from sqlalchemy import text

from mangrove_ai.change import classify_extent_change
from mangrove_ai.config import settings
from mangrove_ai.db import get_session
from mangrove_ai.gee_client import CompositeRequest, GEENotConfiguredError, gee_client
from mangrove_ai.geo import ensure_grid_cells, resolve_aoi
from mangrove_ai.health import canopy_condition_indicator
from mangrove_ai.rag import router as rag_router
from mangrove_ai.risk_evidence import local_risk_evidence
from mangrove_ai.schemas import ToolResponse
from mangrove_ai.suitability import SuitabilityFeatures, compute_suitability


def _aoi_kwargs(aoi_id, bbox):
    return {"aoi_id": aoi_id, "bbox": bbox}


def query_sentinel(aoi_id: str | None = None, bbox: tuple | None = None,
                    period_start: str | None = None, period_end: str | None = None,
                    composite_type: str = "annual") -> ToolResponse:
    aoi = resolve_aoi(aoi_id, bbox)
    params = {**_aoi_kwargs(aoi_id, bbox), "period_start": period_start, "period_end": period_end, "composite_type": composite_type}

    if not gee_client.is_configured:
        return ToolResponse(
            data=None,
            source=[settings.s2_sr_collection, settings.s2_cloud_prob_collection],
            parameters=params,
            confidence=None,
            limitations=["GEE credentials not configured in this deployment — no live Sentinel-2 query was made. This is not a fabricated result."],
        )

    from datetime import date

    request = CompositeRequest(
        aoi_geojson=__import__("json").loads(aoi["geojson_str"]),
        period_start=date.fromisoformat(period_start) if period_start else date(2023, 1, 1),
        period_end=date.fromisoformat(period_end) if period_end else date(2023, 12, 31),
        composite_type=composite_type,
    )
    try:
        composite = gee_client.build_annual_composite(request)
        return ToolResponse(
            data={"composite_ready": True, "ee_object_repr": str(composite)},
            source=[settings.s2_sr_collection, settings.s2_cloud_prob_collection],
            parameters=params,
            confidence=None,
            limitations=[],
        )
    except GEENotConfiguredError as e:
        return ToolResponse(data=None, source=[settings.s2_sr_collection], parameters=params, limitations=[str(e)])


def get_mangrove_map(aoi_id: str | None = None, bbox: tuple | None = None, year: int | None = None) -> ToolResponse:
    aoi = resolve_aoi(aoi_id, bbox)
    cells = ensure_grid_cells(aoi["bounds"])
    cell_ids = [c["cell_id"] for c in cells]

    with get_session() as session:
        rows = session.execute(
            text("""SELECT cell_id, probability, predicted_class, model_id FROM mangrove_probability_cells
                     WHERE cell_id = ANY(:cell_ids)"""),
            {"cell_ids": cell_ids},
        ).mappings().all()

    limitations = []
    if not rows:
        limitations.append("No mangrove_probability_cells rows for this AOI yet — the RF/GBM classifier has not been run against real ingested imagery for this area.")

    return ToolResponse(
        data={"cells": [dict(r) for r in rows], "grid_cell_count": len(cells)},
        source=["mangrove_ai.models.baseline"],
        parameters={**_aoi_kwargs(aoi_id, bbox), "year": year},
        confidence=(float(np.mean([r["probability"] for r in rows])) if rows else None),
        limitations=limitations,
    )


def get_mangrove_timeseries(aoi_id: str | None = None, bbox: tuple | None = None) -> ToolResponse:
    aoi = resolve_aoi(aoi_id, bbox)
    with get_session() as session:
        if aoi["aoi_id"]:
            rows = session.execute(
                text("SELECT year, gain_km2, loss_km2, net_km2, total_extent_km2 FROM extent_timeseries_cache WHERE aoi_id = :aoi_id ORDER BY year"),
                {"aoi_id": aoi["aoi_id"]},
            ).mappings().all()
        else:
            rows = []

    limitations = []
    if not rows:
        limitations.append("No CGMD-Extent30-derived extent_timeseries_cache rows for this AOI yet — requires GEE credentials and a materialization run.")

    return ToolResponse(
        data=[dict(r) for r in rows],
        source=["projects/mangrovedatahub2_assets/CGMD-Extent30SO"],
        parameters=_aoi_kwargs(aoi_id, bbox),
        limitations=limitations,
    )


def query_gmw(aoi_id: str | None = None, bbox: tuple | None = None) -> ToolResponse:
    aoi = resolve_aoi(aoi_id, bbox)
    x0, y0, x1, y1 = aoi["bounds"]
    with get_session() as session:
        rows = session.execute(
            text("""SELECT id, gmw_feature_id, source_version, area_km2, ST_AsGeoJSON(geom) AS geojson
                     FROM gmw_baseline_vectors WHERE ST_Intersects(geom, ST_MakeEnvelope(:x0,:y0,:x1,:y1,4326))"""),
            {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
        ).mappings().all()

    limitations = [] if rows else ["No Global Mangrove Watch v4 vectors ingested for this AOI yet — GMW is blocked from this sandbox's network; upload the source file to ingest."]
    return ToolResponse(data=[dict(r) for r in rows], source=["gmw"], parameters=_aoi_kwargs(aoi_id, bbox), limitations=limitations)


def query_gbif(aoi_id: str | None = None, bbox: tuple | None = None, species: str | None = None) -> ToolResponse:
    aoi = resolve_aoi(aoi_id, bbox)
    x0, y0, x1, y1 = aoi["bounds"]
    with get_session() as session:
        rows = session.execute(
            text("""SELECT occurrence_id, species, event_date, basis_of_record, ST_AsGeoJSON(geom) AS geojson
                     FROM gbif_observations
                     WHERE ST_Intersects(geom, ST_MakeEnvelope(:x0,:y0,:x1,:y1,4326))
                       AND (CAST(:species AS text) IS NULL OR species = CAST(:species AS text))"""),
            {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "species": species},
        ).mappings().all()

    limitations = [] if rows else ["No GBIF occurrence records ingested for this AOI yet."]
    return ToolResponse(data=[dict(r) for r in rows], source=["GBIF"], parameters={**_aoi_kwargs(aoi_id, bbox), "species": species}, limitations=limitations)


def query_cgmd(aoi_id: str | None = None, bbox: tuple | None = None, year: int | None = None) -> ToolResponse:
    aoi = resolve_aoi(aoi_id, bbox)
    cells = ensure_grid_cells(aoi["bounds"])
    cell_ids = [c["cell_id"] for c in cells]
    with get_session() as session:
        extent_rows = session.execute(
            text("SELECT cell_id, year, is_mangrove FROM cgmd_extent_annual WHERE cell_id = ANY(:cids) AND (CAST(:year AS int) IS NULL OR year = CAST(:year AS int))"),
            {"cids": cell_ids, "year": year},
        ).mappings().all()
        afcc_rows = session.execute(
            text("SELECT cell_id, year, fractional_cover FROM cgmd_afcc_annual WHERE cell_id = ANY(:cids) AND (CAST(:year AS int) IS NULL OR year = CAST(:year AS int))"),
            {"cids": cell_ids, "year": year},
        ).mappings().all()

    limitations = []
    if not extent_rows and not afcc_rows:
        limitations.append("No CGMD-Extent30/AFCC30 rows ingested for this AOI yet. Note: CGMD_AFCC_ASSET_ID must be independently confirmed before use — 'CGMD-AFCC305' is not assumed valid (see mangrove_ai.config).")

    return ToolResponse(
        data={"extent": [dict(r) for r in extent_rows], "canopy_cover": [dict(r) for r in afcc_rows]},
        source=[settings.cgmd_extent_asset_id, settings.cgmd_afcc_asset_id or "CGMD-AFCC30 (asset id not yet configured)"],
        parameters={**_aoi_kwargs(aoi_id, bbox), "year": year},
        limitations=limitations,
    )


def calculate_change(aoi_id: str | None = None, bbox: tuple | None = None,
                      period_start: int | None = None, period_end: int | None = None) -> ToolResponse:
    ts = get_mangrove_timeseries(aoi_id, bbox)
    extent_by_year = {r["year"]: r["total_extent_km2"] for r in ts.data} if ts.data else {}
    if period_start:
        extent_by_year = {y: v for y, v in extent_by_year.items() if y >= period_start}
    if period_end:
        extent_by_year = {y: v for y, v in extent_by_year.items() if y <= period_end}

    if len(extent_by_year) < 2:
        return ToolResponse(
            data=None, source=ts.source, parameters={**_aoi_kwargs(aoi_id, bbox), "period_start": period_start, "period_end": period_end},
            limitations=ts.limitations + ["Fewer than 2 years of extent data in range — cannot compute a change trend."],
        )

    result = classify_extent_change(extent_by_year, sources=ts.source)
    return ToolResponse(
        data={"change_class": result.change_class, "change_rate_km2_per_yr": result.change_rate_km2_per_yr, "result_type": result.result_type},
        source=result.sources,
        parameters={**_aoi_kwargs(aoi_id, bbox), "period_start": period_start, "period_end": period_end},
        limitations=ts.limitations,
    )


def calculate_health_indicators(aoi_id: str | None = None, bbox: tuple | None = None, year: int | None = None) -> ToolResponse:
    aoi = resolve_aoi(aoi_id, bbox)
    cells = ensure_grid_cells(aoi["bounds"])
    cell_ids = [c["cell_id"] for c in cells]

    with get_session() as session:
        rows = session.execute(
            text("""SELECT s.cell_id, s.index_name, s.value FROM spectral_index_values s
                     WHERE s.cell_id = ANY(:cids) AND s.index_name IN ('NDVI','EVI','NDMI')"""),
            {"cids": cell_ids},
        ).mappings().all()

    if not rows:
        return ToolResponse(
            data=None, source=["mangrove_ai.health"], parameters={**_aoi_kwargs(aoi_id, bbox), "year": year},
            limitations=["No spectral_index_values ingested for this AOI yet — requires a materialized Sentinel-2 composite."],
        )

    by_cell: dict[int, dict[str, float]] = {}
    for r in rows:
        by_cell.setdefault(r["cell_id"], {})[r["index_name"]] = r["value"]

    results = []
    for cell_id, indices in by_cell.items():
        result = canopy_condition_indicator(indices)
        results.append({"cell_id": cell_id, **result.__dict__})

    return ToolResponse(
        data=results,
        source=["mangrove_ai.health", settings.s2_sr_collection],
        parameters={**_aoi_kwargs(aoi_id, bbox), "year": year},
        confidence=None,
        limitations=[],
    )


def calculate_restoration_suitability(aoi_id: str | None = None, bbox: tuple | None = None) -> ToolResponse:
    """The central tool. Gathers whatever features are actually available
    per cell from the DB and scores each — see mangrove_ai.suitability.
    With no ingested composites/labels yet, this returns EXCLUDED/LOW-only
    results built from an empty feature set (honest, not fabricated) — the
    code path is real and will produce real HIGH/VERY_HIGH candidates once
    Sentinel-2 + CGMD + GMW data is materialized for the AOI.
    """
    aoi = resolve_aoi(aoi_id, bbox)
    cells = ensure_grid_cells(aoi["bounds"])
    cell_ids = [c["cell_id"] for c in cells]
    model_version = "suitability-rules-v0.1.0"

    with get_session() as session:
        mangrove_prob = {r["cell_id"]: r["probability"] for r in session.execute(
            text("SELECT cell_id, probability FROM mangrove_probability_cells WHERE cell_id = ANY(:cids)"), {"cids": cell_ids}).mappings()}
        historical = {r["cell_id"] for r in session.execute(
            text("SELECT DISTINCT cell_id FROM cgmd_extent_annual WHERE cell_id = ANY(:cids) AND is_mangrove"), {"cids": cell_ids}).mappings()}
        indices_rows = session.execute(
            text("SELECT cell_id, index_name, value FROM spectral_index_values WHERE cell_id = ANY(:cids)"), {"cids": cell_ids}).mappings()
        condition = {r["cell_id"]: r["stress_flag"] for r in session.execute(
            text("SELECT cell_id, stress_flag FROM canopy_condition_cells WHERE cell_id = ANY(:cids)"), {"cids": cell_ids}).mappings()}
        exclusions = {r["cell_id"]: r["layer_type"] for r in session.execute(
            text("""SELECT g.cell_id, l.layer_type FROM grid_cells g
                     JOIN spatial_context_layers l ON ST_Intersects(g.geom, l.geom)
                     WHERE g.cell_id = ANY(:cids) AND l.layer_type IN ('built_up','road')"""), {"cids": cell_ids}).mappings()}

    indices_by_cell: dict[int, dict[str, float]] = {}
    for r in indices_rows:
        indices_by_cell.setdefault(r["cell_id"], {})[r["index_name"]] = r["value"]

    results = []
    sources_used: set[str] = set()
    run_id = None
    with get_session() as session:
        run_id = session.execute(
            text("""INSERT INTO suitability_runs (aoi_id, model_id, feature_set)
                     SELECT :aoi_id, m.model_id, :feature_set FROM models m WHERE m.version = :model_version LIMIT 1
                     RETURNING run_id"""),
            {"aoi_id": aoi["aoi_id"], "feature_set": '{"note":"see suitability_cells.data_sources per cell"}', "model_version": model_version},
        ).scalar()

    for cell in cells:
        cid = cell["cell_id"]
        idx = indices_by_cell.get(cid, {})
        features = SuitabilityFeatures(
            current_mangrove_probability=mangrove_prob.get(cid),
            historical_mangrove_presence=(cid in historical) if historical or mangrove_prob else None,
            ndvi=idx.get("NDVI"), evi=idx.get("EVI"), ndmi=idx.get("NDMI"),
            ndwi=idx.get("NDWI"), mndwi=idx.get("MNDWI"),
            salinity_proxy=idx.get("SI"),
            current_stress_score=(1.0 if condition.get(cid) else (0.0 if cid in condition else None)),
            built_up_exclusion=(exclusions.get(cid) == "built_up") if cid in exclusions else None,
            road_infrastructure_exclusion=(exclusions.get(cid) == "road") if cid in exclusions else None,
            data_sources=tuple(sorted({
                *(["mangrove_ai.models.baseline"] if cid in mangrove_prob else []),
                *(["cgmd-extent30"] if historical else []),
                *([settings.s2_sr_collection] if idx else []),
            })),
        )
        result = compute_suitability(features)
        sources_used.update(result.data_sources)

        risk = local_risk_evidence(cell["lon"], cell["lat"])

        if run_id and result.classification != "EXCLUDED":
            with get_session() as session:
                session.execute(
                    text("""INSERT INTO suitability_cells (run_id, cell_id, suitability_score, confidence, classification,
                                reason_codes, data_sources, model_version, local_ecological_risk_evidence)
                             VALUES (:run_id, :cell_id, :score, :confidence, :classification, :reasons, :sources, :model_version, :risk)
                             ON CONFLICT (run_id, cell_id) DO NOTHING"""),
                    {"run_id": run_id, "cell_id": cid, "score": result.suitability_score, "confidence": result.confidence,
                     "classification": result.classification, "reasons": result.reason_codes, "sources": result.data_sources,
                     "model_version": model_version, "risk": risk["has_evidence"]},
                )

        results.append({
            "cell_id": cid, "lon": cell["lon"], "lat": cell["lat"],
            "suitability_score": result.suitability_score, "confidence": result.confidence,
            "classification": result.classification, "reason_codes": result.reason_codes,
            "data_sources": result.data_sources, "model_version": model_version,
            "local_ecological_risk_evidence": risk["has_evidence"],
            "field_validation_label": result.field_validation_label,
        })

    limitations = []
    if not mangrove_prob and not historical and not indices_by_cell:
        limitations.append(
            "No Sentinel-2, CGMD, or GMW data has been ingested for this AOI yet, so every cell scored with an "
            "empty feature set (low confidence, non-EXCLUDED classes unlikely). This is the real scoring engine "
            "running on real (currently absent) data, not a placeholder result."
        )

    return ToolResponse(
        data={"run_id": str(run_id) if run_id else None, "cells": results},
        source=sorted(sources_used) or ["mangrove_ai.suitability"],
        parameters=_aoi_kwargs(aoi_id, bbox),
        model_version=model_version,
        limitations=limitations,
    )


def run_forecast(aoi_id: str | None = None, bbox: tuple | None = None,
                  horizon_year: int = 2030, model_type: str = "naive") -> ToolResponse:
    ts = get_mangrove_timeseries(aoi_id, bbox)
    if not ts.data or len(ts.data) < 3:
        return ToolResponse(data=None, source=ts.source, parameters={**_aoi_kwargs(aoi_id, bbox), "horizon_year": horizon_year, "model_type": model_type},
                             limitations=ts.limitations + ["Fewer than 3 years of extent data — cannot fit even a naive baseline."])

    years = np.array([r["year"] for r in ts.data])
    values = np.array([r["total_extent_km2"] for r in ts.data])

    split = int(len(years) * 0.8)  # chronological split, no shuffling
    train_y, train_v = years[:split], values[:split]
    test_y, test_v = years[split:], values[split:]

    naive_pred = np.full(len(test_v), train_v[-1])
    naive_mae = float(np.mean(np.abs(test_v - naive_pred)))

    slope, intercept = np.polyfit(train_y, train_v, 1)
    linear_pred_test = slope * test_y + intercept
    linear_mae = float(np.mean(np.abs(test_v - linear_pred_test)))

    if model_type in ("gru", "lstm"):
        return ToolResponse(
            data=None, source=ts.source, parameters={**_aoi_kwargs(aoi_id, bbox), "horizon_year": horizon_year, "model_type": model_type},
            limitations=[f"{model_type.upper()} is not trained yet — per build strategy, a GRU/LSTM is only justified once naive "
                         f"(MAE={naive_mae:.3f}) and linear (MAE={linear_mae:.3f}) baselines are established and a deep model "
                         "is shown to beat them on this AOI's chronologically split data."],
        )

    chosen_pred = slope * horizon_year + intercept
    return ToolResponse(
        data={
            "label": "MODEL PREDICTION",
            "model_type": "linear_regression" if model_type == "linear" else "naive_baseline",
            "horizon_year": horizon_year,
            "predicted_extent_km2": float(chosen_pred) if model_type == "linear" else float(train_v[-1]),
            "baseline_comparison": {"naive_mae": naive_mae, "linear_mae": linear_mae},
        },
        source=ts.source,
        parameters={**_aoi_kwargs(aoi_id, bbox), "horizon_year": horizon_year, "model_type": model_type},
        confidence=None,
        limitations=["Chronological train/test split, no random shuffling. MAE reported on held-out final years only."],
    )


def search_ragflow(query: str, location: str | None = None, category: str | None = None, top_k: int = 5) -> ToolResponse:
    result = rag_router.search(query, location=location, category=category, top_k=top_k)
    return ToolResponse(
        data=result["results"],
        source=[settings.rag_backend],
        parameters={"query": query, "location": location, "category": category, "top_k": top_k},
        confidence=(max((r["score"] for r in result["results"]), default=0.0) if result["results"] else 0.0),
        limitations=[result["message"]] if result["insufficient_evidence"] else [],
    )


def generate_map(layer: str, aoi_id: str | None = None, bbox: tuple | None = None) -> ToolResponse:
    """Returns structured GeoJSON-ready payload for a named layer, for the
    frontend's MapLibre map to render — never a rendered image."""
    dispatch = {
        "mangrove_extent": get_mangrove_map,
        "gmw_baseline": query_gmw,
        "gbif": query_gbif,
        "cgmd": query_cgmd,
        "restoration_suitability": calculate_restoration_suitability,
    }
    if layer not in dispatch:
        return ToolResponse(data=None, source=[], parameters={"layer": layer}, limitations=[f"Unknown layer '{layer}'. Available: {list(dispatch)}"])
    inner = dispatch[layer](aoi_id, bbox)
    return ToolResponse(data=inner.data, source=inner.source, parameters={"layer": layer, **inner.parameters},
                         model_version=inner.model_version, confidence=inner.confidence, limitations=inner.limitations)


def generate_chart(chart_type: str, aoi_id: str | None = None, bbox: tuple | None = None) -> ToolResponse:
    dispatch = {
        "extent_timeseries": get_mangrove_timeseries,
        "health_indicators": calculate_health_indicators,
    }
    if chart_type not in dispatch:
        return ToolResponse(data=None, source=[], parameters={"chart_type": chart_type}, limitations=[f"Unknown chart_type '{chart_type}'. Available: {list(dispatch)}"])
    inner = dispatch[chart_type](aoi_id, bbox)
    return ToolResponse(data=inner.data, source=inner.source, parameters={"chart_type": chart_type, **inner.parameters},
                         model_version=inner.model_version, confidence=inner.confidence, limitations=inner.limitations)


def generate_report(aoi_id: str | None = None, bbox: tuple | None = None, question: str | None = None) -> ToolResponse:
    """Assembles the OBSERVED / DERIVED / SCIENTIFIC EVIDENCE / MODEL OUTPUT /
    LIMITATIONS envelope from the other tools — used directly by Hermes'
    rule-based planner (see services/hermes)."""
    timeseries = get_mangrove_timeseries(aoi_id, bbox)
    change = calculate_change(aoi_id, bbox)
    suitability = calculate_restoration_suitability(aoi_id, bbox)
    evidence = search_ragflow(question or "mangrove restoration suitability Karachi", top_k=5)

    high_candidates = [c for c in suitability.data["cells"] if c["classification"] in ("HIGH", "VERY_HIGH")] if suitability.data else []

    envelope = {
        "observed_data": [f"{len(timeseries.data)} years of extent observations available" if timeseries.data else "No extent observations ingested for this AOI."],
        "derived_analysis": [f"Change class: {change.data['change_class']}" if change.data else "Change trend not computable (insufficient data)."],
        "scientific_evidence": evidence.data,
        "model_output": [f"{len(high_candidates)} HIGH/VERY_HIGH restoration candidate cells (suitability model {suitability.model_version})"],
        "limitations": timeseries.limitations + change.limitations + suitability.limitations + evidence.limitations,
    }
    return ToolResponse(
        data=envelope,
        source=sorted(set(timeseries.source + change.source + suitability.source + evidence.source)),
        parameters={**_aoi_kwargs(aoi_id, bbox), "question": question},
        model_version=suitability.model_version,
        limitations=[],
    )


def get_model_metadata(task: str | None = None, version: str | None = None) -> ToolResponse:
    with get_session() as session:
        rows = session.execute(
            text("""SELECT model_id, task, version, algorithm, metrics, feature_importance, promoted, trained_at
                     FROM models WHERE (CAST(:task AS text) IS NULL OR task = CAST(:task AS text))
                       AND (CAST(:version AS text) IS NULL OR version = CAST(:version AS text))
                     ORDER BY trained_at DESC"""),
            {"task": task, "version": version},
        ).mappings().all()
    return ToolResponse(data=[dict(r) for r in rows], source=["models"], parameters={"task": task, "version": version},
                         limitations=[] if rows else ["No models registered yet for this filter."])
