import json
from dataclasses import asdict
from typing import Annotated

from langchain.tools import BaseTool, ToolRuntime, tool

from bank_sales_agent.application.artifacts import AgentArtifact, Customer360Artifact
from bank_sales_agent.application.use_cases.customer_360 import GetCustomer360
from bank_sales_agent.infrastructure.agent.context import AgentContext


def build_customer_360_tools(get_customer_360: GetCustomer360) -> list[BaseTool]:
    @tool(response_format="content_and_artifact")
    async def customer_360(
        rut: Annotated[str, "RUT chileno del cliente, con digito verificador"],
        runtime: ToolRuntime[AgentContext],
    ) -> tuple[str, AgentArtifact]:
        """Obtiene la vista consolidada 360 de un cliente autorizado."""
        result = await get_customer_360.execute(runtime.context.principal, rut)
        content = json.dumps(asdict(result), ensure_ascii=False, default=str)
        return content, Customer360Artifact(result)

    return [customer_360]
