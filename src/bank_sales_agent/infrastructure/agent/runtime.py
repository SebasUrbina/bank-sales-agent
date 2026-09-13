from typing import Any

from langchain.agents import create_agent

from bank_sales_agent.infrastructure.agent.context import AgentContext
from bank_sales_agent.infrastructure.agent.middleware import harness_middlewares
from bank_sales_agent.infrastructure.agent.tools.registry import ToolRegistry


def build_agent(model: str, registry: ToolRegistry) -> Any:
    return create_agent(
        model=model,
        tools=registry.all(),
        middleware=harness_middlewares(registry),
        context_schema=AgentContext,
    )
