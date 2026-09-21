import json

import pytest

from mangrove_ai.hermes.tool_specs import TOOL_SPECS
from mangrove_ai.mcp_server import call_tool, list_tools


@pytest.mark.asyncio
async def test_list_tools_exposes_every_spec():
    tools = await list_tools()
    names = {t.name for t in tools}
    assert names == {spec["name"] for spec in TOOL_SPECS}


@pytest.mark.asyncio
async def test_list_tools_never_exposes_model_promotion():
    tools = await list_tools()
    assert "promote_model" not in {t.name for t in tools}


@pytest.mark.asyncio
async def test_call_tool_dispatches_and_returns_json(small_bbox):
    result = await call_tool("get_mangrove_timeseries", {"bbox": list(small_bbox)})
    payload = json.loads(result[0].text)
    assert "data" in payload
    assert "limitations" in payload


@pytest.mark.asyncio
async def test_call_tool_unknown_name_returns_error_not_a_crash():
    result = await call_tool("not_a_real_tool", {})
    payload = json.loads(result[0].text)
    assert "error" in payload
