"""Hermes: the autonomous orchestrator. It never computes a geospatial
result itself — every fact in its answer comes from a tool call in
mangrove_ai.hermes.tool_specs.TOOL_DISPATCH, logged to hermes_runs /
hermes_tool_calls / evidence_ledger for full audit.

Two planning modes:
  - rule_based (default, always available): a fixed, documented sequence
    matching the build spec's "MAIN USER WORKFLOW" — deterministic, no LLM
    call, always testable in this sandbox.
  - llm: when ANTHROPIC_API_KEY is configured, Claude drives tool selection
    via the standard tool-use loop over TOOL_SPECS. Falls back to
    rule_based automatically if no key is configured — this is a graceful
    degradation, not a silent fabrication, and is reported in the answer's
    `planner_mode`.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from sqlalchemy import text

from mangrove_ai.config import settings
from mangrove_ai.db import get_session
from mangrove_ai.geo import resolve_aoi
from mangrove_ai.hermes.tool_specs import TOOL_DISPATCH, TOOL_SPECS
from mangrove_ai.schemas import ToolResponse

MAX_LLM_TOOL_ROUNDS = 8


def _log_run(question: str, aoi_id: str | None, planner_mode: str) -> str:
    with get_session() as session:
        run_id = session.execute(
            text("INSERT INTO hermes_runs (user_question, aoi_id, planner_mode) VALUES (:q, :aoi, :mode) RETURNING hermes_run_id"),
            {"q": question, "aoi": aoi_id, "mode": planner_mode},
        ).scalar()
    return str(run_id)


def _log_tool_call(hermes_run_id: str, tool_name: str, parameters: dict, result, duration_ms: int) -> None:
    summary = result.model_dump() if isinstance(result, ToolResponse) else {"data": result}
    # trim large payloads before logging — the audit trail records provenance, not a full data dump
    trimmed = {**summary, "data": _truncate(summary.get("data"))}
    with get_session() as session:
        session.execute(
            text("""INSERT INTO hermes_tool_calls (hermes_run_id, tool_name, parameters, result_summary, duration_ms)
                     VALUES (:run_id, :tool, CAST(:params AS jsonb), CAST(:result AS jsonb), :duration)"""),
            {"run_id": hermes_run_id, "tool": tool_name, "params": json.dumps(parameters, default=str),
             "result": json.dumps(trimmed, default=str), "duration": duration_ms},
        )


def _truncate(data, max_items: int = 5):
    if isinstance(data, list):
        return data[:max_items] + ([f"... {len(data) - max_items} more"] if len(data) > max_items else [])
    if isinstance(data, dict):
        return {k: _truncate(v, max_items) for k, v in data.items()}
    return data


def _finish_run(hermes_run_id: str, final_answer: dict, status: str = "done") -> None:
    with get_session() as session:
        session.execute(
            text("UPDATE hermes_runs SET status = :status, final_answer = CAST(:answer AS jsonb), finished_at = now() WHERE hermes_run_id = :id"),
            {"status": status, "answer": json.dumps(final_answer, default=str), "id": hermes_run_id},
        )


def _call_tool(hermes_run_id: str, tool_name: str, args: dict):
    if tool_name not in TOOL_DISPATCH:
        raise ValueError(f"Unknown tool '{tool_name}'")
    start = time.monotonic()
    result = TOOL_DISPATCH[tool_name](args)
    duration_ms = int((time.monotonic() - start) * 1000)
    _log_tool_call(hermes_run_id, tool_name, args, result, duration_ms)
    return result


def _rule_based_plan(hermes_run_id: str, aoi_id: str | None, bbox: tuple | None, question: str) -> dict:
    """The documented 14-step workflow from the build spec, steps 1-13
    (step 14, the field-validation statement, is enforced inside
    calculate_restoration_suitability itself, not a separate step here)."""
    aoi_kwargs = {"aoi_id": aoi_id, "bbox": list(bbox) if bbox else None}

    sentinel = _call_tool(hermes_run_id, "query_sentinel", aoi_kwargs)
    gmw = _call_tool(hermes_run_id, "query_gmw", aoi_kwargs)
    cgmd = _call_tool(hermes_run_id, "query_cgmd", aoi_kwargs)
    mangrove_map = _call_tool(hermes_run_id, "get_mangrove_map", aoi_kwargs)
    health = _call_tool(hermes_run_id, "calculate_health_indicators", aoi_kwargs)
    change = _call_tool(hermes_run_id, "calculate_change", aoi_kwargs)
    suitability = _call_tool(hermes_run_id, "calculate_restoration_suitability", aoi_kwargs)
    evidence = _call_tool(hermes_run_id, "search_ragflow", {"query": question, **aoi_kwargs})
    report = _call_tool(hermes_run_id, "generate_report", {**aoi_kwargs, "question": question})

    with get_session() as session:
        for c in (suitability.data or {}).get("cells", []):
            if c["classification"] in ("HIGH", "VERY_HIGH"):
                session.execute(
                    text("""INSERT INTO evidence_ledger (hermes_run_id, evidence_type, ref_description)
                             VALUES (:run_id, 'model_output', :ref)"""),
                    {"run_id": hermes_run_id, "ref": f"suitability cell {c['cell_id']}: {c['classification']} ({c['suitability_score']})"},
                )
        for r in evidence.data or []:
            session.execute(
                text("""INSERT INTO evidence_ledger (hermes_run_id, evidence_type, doc_id, ref_description)
                         VALUES (:run_id, 'rag_citation', :doc_id, :ref)"""),
                {"run_id": hermes_run_id, "doc_id": r["doc_id"], "ref": f"{r['title']} p.{r.get('page')}"},
            )

    high_very_high = [c for c in (suitability.data or {}).get("cells", []) if c["classification"] in ("HIGH", "VERY_HIGH")]

    return {
        "answer": report.data,
        "map_layers": {"restoration_suitability": suitability.data, "mangrove_extent": mangrove_map.data, "gmw_baseline": gmw.data},
        "candidate_count": len(high_very_high),
        "candidates": high_very_high,
        "citations": evidence.data,
        "field_validation_required": True,
        "field_validation_statement": "Candidate restoration area — field validation required.",
        "steps_executed": ["query_sentinel", "query_gmw", "query_cgmd", "get_mangrove_map", "calculate_health_indicators",
                            "calculate_change", "calculate_restoration_suitability", "search_ragflow", "generate_report"],
    }


def _llm_plan(hermes_run_id: str, aoi_id: str | None, bbox: tuple | None, question: str) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    system_prompt = (
        "You are Hermes, the orchestration layer for Mangrove AI Intelligence. "
        "You must call tools to get every geospatial fact — never invent coordinates, "
        "extent values, species, pollution levels, or model accuracy. When you have "
        "gathered enough evidence, call calculate_restoration_suitability and "
        "search_ragflow before your final answer, and always state that any HIGH/"
        "VERY_HIGH candidate requires field validation. Never say 'plant mangroves here.'"
    )
    messages = [{"role": "user", "content": f"{question}\nAOI: aoi_id={aoi_id}, bbox={bbox}"}]
    anthropic_tools = [{"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]} for t in TOOL_SPECS]

    for _ in range(MAX_LLM_TOOL_ROUNDS):
        response = client.messages.create(
            model=settings.hermes_model, max_tokens=2048, system=system_prompt,
            tools=anthropic_tools, messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            final_text = "".join(b.text for b in response.content if b.type == "text")
            return {"answer_text": final_text, "steps_executed": [m["tool_name"] for m in messages if isinstance(m, dict) and "tool_name" in m]}

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                result = _call_tool(hermes_run_id, block.name, block.input)
                content = result.model_dump_json() if isinstance(result, ToolResponse) else json.dumps(result, default=str)
            except Exception as e:
                content = json.dumps({"error": str(e)})
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": content})
        messages.append({"role": "user", "content": tool_results})

    return {"answer_text": "Reached MAX_LLM_TOOL_ROUNDS without a final answer.", "steps_executed": []}


def run(question: str, aoi_id: str | None = None, bbox: tuple | None = None) -> dict:
    resolved = resolve_aoi(aoi_id, bbox)
    effective_aoi_id = resolved["aoi_id"]

    use_llm = bool(settings.anthropic_api_key)
    planner_mode = "llm" if use_llm else "rule_based"
    hermes_run_id = _log_run(question, effective_aoi_id, planner_mode)

    try:
        if use_llm:
            try:
                result = _llm_plan(hermes_run_id, aoi_id, bbox, question)
            except Exception as e:  # graceful degradation, never a silent fabrication
                result = _rule_based_plan(hermes_run_id, aoi_id, bbox, question)
                result["llm_fallback_reason"] = str(e)
                planner_mode = "rule_based (llm attempt failed)"
        else:
            result = _rule_based_plan(hermes_run_id, aoi_id, bbox, question)

        result["hermes_run_id"] = hermes_run_id
        result["planner_mode"] = planner_mode
        result["generated_at"] = datetime.now(timezone.utc).isoformat()
        _finish_run(hermes_run_id, result, status="done")
        return result
    except Exception:
        _finish_run(hermes_run_id, {"error": "Hermes run failed"}, status="failed")
        raise
