from collections.abc import Iterable

from langchain.tools import BaseTool

from bank_sales_agent.application.agent.catalog import TOOL_CATALOG, visible_tool_names
from bank_sales_agent.domain.models import Principal
from bank_sales_agent.infrastructure.agent.tools.customer_360 import customer_360
from bank_sales_agent.infrastructure.agent.tools.customer_portfolio import (
    list_prioritized_customers,
)


class ToolRegistry:
    def __init__(self, tools: Iterable[BaseTool]) -> None:
        self._by_name = {tool.name: tool for tool in tools}
        expected = {spec.name for spec in TOOL_CATALOG}
        missing = expected - self._by_name.keys()
        unexpected = self._by_name.keys() - expected
        if missing or unexpected:
            raise ValueError(
                f"Tool registry desalineado; missing={sorted(missing)}, "
                f"unexpected={sorted(unexpected)}"
            )

    def all(self) -> list[BaseTool]:
        return list(self._by_name.values())

    def for_principal(self, principal: Principal) -> list[BaseTool]:
        visible = visible_tool_names(principal)
        return [tool for name, tool in self._by_name.items() if name in visible]


def build_tool_registry() -> ToolRegistry:
    return ToolRegistry([customer_360, list_prioritized_customers])
