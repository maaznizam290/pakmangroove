"""The required end-to-end test:
Question -> Hermes -> RAGFlow/fallback -> Sentinel/Geo tools -> suitability
model -> visualization data -> cited response.

Runs the real rule-based Hermes planner (no ANTHROPIC_API_KEY in this
environment, so the LLM planner path isn't exercised here — see
mangrove_ai.hermes.orchestrator for that path) against the real DB, and
asserts on the full audit trail it leaves behind, not just its return
value.
"""

from sqlalchemy import text

from mangrove_ai.db import get_session
from mangrove_ai.hermes.orchestrator import run

QUESTION = "Show me where mangrove restoration may be suitable around Karachi and explain why."


def test_full_hermes_pipeline_question_to_cited_answer(small_bbox, small_cells):
    # `small_cells` isn't used directly — it's requested so its teardown
    # cleans up the grid cells Hermes materializes via query_cgmd /
    # get_mangrove_map / calculate_restoration_suitability along the way.
    result = run(QUESTION, bbox=small_bbox)

    # 1. Hermes ran the documented tool sequence, not an invented shortcut
    expected_steps = {
        "query_sentinel", "query_gmw", "query_cgmd", "get_mangrove_map",
        "calculate_health_indicators", "calculate_change",
        "calculate_restoration_suitability", "search_ragflow", "generate_report",
    }
    assert expected_steps <= set(result["steps_executed"])
    assert result["planner_mode"] == "rule_based"

    # 2. The answer separates OBSERVED / DERIVED / SCIENTIFIC EVIDENCE / MODEL OUTPUT / LIMITATIONS
    answer = result["answer"]
    for key in ("observed_data", "derived_analysis", "scientific_evidence", "model_output", "limitations"):
        assert key in answer

    # 3. Visualization data was produced (map layers + candidate list), even if empty pending real data
    assert "restoration_suitability" in result["map_layers"]
    assert isinstance(result["candidates"], list)

    # 4. The field-validation rule is enforced on the response itself, not just in the DB constraint
    assert result["field_validation_required"] is True
    assert result["field_validation_statement"] == "Candidate restoration area — field validation required."
    for candidate in result["candidates"]:
        assert candidate["classification"] in ("HIGH", "VERY_HIGH")
        assert candidate["field_validation_label"] == result["field_validation_statement"]

    # 5. Every tool call is in the audit trail (hermes_tool_calls), and the
    #    run itself is recorded with a final status — this is what makes
    #    "never invent a result" enforceable after the fact.
    with get_session() as session:
        run_row = session.execute(
            text("SELECT status, user_question, planner_mode FROM hermes_runs WHERE hermes_run_id = :id"),
            {"id": result["hermes_run_id"]},
        ).mappings().first()
        tool_call_names = {
            r["tool_name"] for r in session.execute(
                text("SELECT tool_name FROM hermes_tool_calls WHERE hermes_run_id = :id"), {"id": result["hermes_run_id"]}
            ).mappings()
        }

    assert run_row["status"] == "done"
    assert run_row["user_question"] == QUESTION
    assert expected_steps <= tool_call_names


def test_hermes_never_invents_plant_here_language(small_bbox, small_cells):
    result = run(QUESTION, bbox=small_bbox)
    import json

    full_text = json.dumps(result, default=str).lower()
    assert "plant mangroves here" not in full_text
