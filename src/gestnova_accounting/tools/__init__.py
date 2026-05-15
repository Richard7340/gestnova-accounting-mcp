"""Tool registry."""
from typing import Any
from ._base import BaseTool


class PingTool(BaseTool):
    name = "ping"
    description = "Health check — returns server status and version."
    input_schema = {"type": "object", "properties": {}, "required": []}

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        from gestnova_accounting import __version__
        return {"status": "ok", "version": __version__}


def get_all_tools() -> list[BaseTool]:
    return [PingTool()]
