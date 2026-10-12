from collections.abc import Iterable

from langchain.tools import BaseTool


class ToolRegistry:
    """Tools anunciadas por MCP para esta sesión; no evalúa permisos locales."""

    def __init__(self, tools: Iterable[BaseTool]) -> None:
        self._by_name: dict[str, BaseTool] = {}
        for tool in tools:
            if tool.name in self._by_name:
                raise ValueError(f"Nombre de tool MCP duplicado: {tool.name}")
            self._by_name[tool.name] = tool

    def all(self) -> list[BaseTool]:
        return list(self._by_name.values())

    def get(self, name: str) -> BaseTool | None:
        return self._by_name.get(name)
