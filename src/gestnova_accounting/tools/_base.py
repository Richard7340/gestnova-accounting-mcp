"""Base class shared by all MCP tools."""
from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    name: str
    description: str
    input_schema: dict[str, Any]

    @abstractmethod
    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        ...
