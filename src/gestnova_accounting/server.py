"""MCP stdio server entrypoint."""
import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool as McpTool, TextContent

from gestnova_accounting.tools import get_all_tools


class AccountingServer:
    """In-process wrapper so tests can call tools without going through stdio."""

    def __init__(self):
        self._tools = {t.name: t for t in get_all_tools()}

    async def list_tools(self) -> list:
        return list(self._tools.values())

    async def call_tool(self, name: str, args: dict) -> dict:
        if name not in self._tools:
            raise ValueError(f"Unknown tool: {name}")
        return await self._tools[name].execute(args)


def build_server() -> AccountingServer:
    return AccountingServer()


async def _run_stdio():
    """Run the actual MCP server over stdio."""
    server = Server("gestnova-accounting")
    in_proc = build_server()

    @server.list_tools()
    async def list_tools_handler() -> list[McpTool]:
        tools = await in_proc.list_tools()
        return [
            McpTool(name=t.name, description=t.description, inputSchema=t.input_schema)
            for t in tools
        ]

    @server.call_tool()
    async def call_tool_handler(name: str, arguments: dict) -> list[TextContent]:
        result = await in_proc.call_tool(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, default=str))]

    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main():
    asyncio.run(_run_stdio())


if __name__ == "__main__":
    main()
