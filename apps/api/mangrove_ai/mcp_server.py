"""MCP server exposing the Mangrove AI Intelligence tools over stdio.

Run with: python -m mangrove_ai.mcp_server

Every tool call goes through mangrove_ai.hermes.tool_specs.TOOL_DISPATCH —
the exact same functions the in-process Hermes orchestrator calls — so an
external MCP client (Claude Desktop, another agent) sees identical
behavior. Note this deliberately does NOT expose model promotion
(mangrove_ai.active_learning.promote_model) as a tool — see that module's
docstring for why.
"""

from __future__ import annotations

import asyncio
import json

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.lowlevel import NotificationOptions

from mangrove_ai.hermes.tool_specs import TOOL_DISPATCH, TOOL_SPECS
from mangrove_ai.schemas import ToolResponse

server = Server("mangrove-ai-intelligence")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [types.Tool(name=t["name"], description=t["description"], inputSchema=t["input_schema"]) for t in TOOL_SPECS]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name not in TOOL_DISPATCH:
        return [types.TextContent(type="text", text=json.dumps({"error": f"Unknown tool '{name}'"}))]
    try:
        result = TOOL_DISPATCH[name](arguments or {})
        payload = result.model_dump() if isinstance(result, ToolResponse) else result
    except Exception as e:
        payload = {"error": str(e), "tool": name, "arguments": arguments}
    return [types.TextContent(type="text", text=json.dumps(payload, default=str, indent=2))]


async def _main() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream,
            InitializationOptions(
                server_name="mangrove-ai-intelligence",
                server_version="0.1.0",
                capabilities=server.get_capabilities(notification_options=NotificationOptions(), experimental_capabilities={}),
            ),
        )


if __name__ == "__main__":
    asyncio.run(_main())
