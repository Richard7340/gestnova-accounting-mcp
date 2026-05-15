"""Smoke test: spawn server in-process and call ping tool."""
import pytest
from gestnova_accounting.server import build_server


@pytest.mark.asyncio
async def test_server_exposes_ping_tool():
    server = build_server()
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]
    assert "ping" in tool_names


@pytest.mark.asyncio
async def test_ping_returns_pong():
    server = build_server()
    result = await server.call_tool("ping", {})
    assert result["status"] == "ok"
    assert "version" in result
