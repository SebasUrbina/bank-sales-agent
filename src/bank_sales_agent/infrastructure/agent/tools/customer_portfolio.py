import json
from dataclasses import asdict
from typing import Annotated

from langchain.tools import BaseTool, ToolRuntime, tool

from bank_sales_agent.application.artifacts import AgentArtifact, PrioritizedCustomersArtifact
from bank_sales_agent.application.dto import ListCustomersQuery
from bank_sales_agent.application.use_cases.list_customers import ListPrioritizedCustomers
from bank_sales_agent.infrastructure.agent.context import AgentContext


def build_customer_portfolio_tools(
    list_customers: ListPrioritizedCustomers,
) -> list[BaseTool]:
    @tool(response_format="content_and_artifact")
    async def list_prioritized_customers(
        runtime: ToolRuntime[AgentContext],
        limit: Annotated[int, "Cantidad de clientes; entre 1 y 100"] = 10,
        segment: Annotated[str | None, "Segmento comercial opcional"] = None,
        min_priority: Annotated[float | None, "Score minimo entre 0 y 1"] = None,
        executive_email: Annotated[
            str | None, "Email del ejecutivo; solo para lideres o admins"
        ] = None,
    ) -> tuple[str, AgentArtifact]:
        """Lista clientes priorizados dentro de la cartera autorizada del usuario."""
        result = list(
            await list_customers.execute(
                runtime.context.principal,
                ListCustomersQuery(limit, segment, min_priority, executive_email),
            )
        )
        content = json.dumps([asdict(item) for item in result], ensure_ascii=False)
        return content, PrioritizedCustomersArtifact(tuple(result))

    return [list_prioritized_customers]
