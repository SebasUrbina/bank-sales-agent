"""Adaptador LangChain: las tools del agente sólo ejecutan llamadas MCP."""

import json
from typing import Any

from fastmcp import Client
from langchain_core.tools import StructuredTool

from bank_sales_agent.application.artifacts import AgentArtifact
from bank_sales_agent.domain.errors import (
    CustomerNotFoundError,
    DomainError,
    ForbiddenError,
    InvalidInputError,
)
from bank_sales_agent.infrastructure.agent.tools.registry import ToolRegistry
from bank_sales_agent.infrastructure.mcp.contracts import ToolResponse
from mcp.types import Tool as McpTool


async def _call(
    client: Client[Any], name: str, arguments: dict[str, Any], request_id: str
) -> tuple[str, AgentArtifact | None]:
    result = await client.call_tool(
        name, arguments, raise_on_error=False, meta={"request_id": request_id}
    )
    if result.is_error:
        for block in result.content:
            if block.type != "text":
                continue
            try:
                error = json.loads(block.text)["error"]
                classes: dict[str, type[DomainError]] = {
                    "access_denied": ForbiddenError,
                    "customer_not_found": CustomerNotFoundError,
                    "invalid_input": InvalidInputError,
                }
                error_type = classes.get(error["code"])
                if error_type:
                    raise error_type(error["message"])
            except (ValueError, KeyError, TypeError):
                continue
        raise RuntimeError("La tool MCP no pudo completar la solicitud")
    response = ToolResponse.model_validate(result.structured_content)
    return response.to_result()


def adapt_mcp_tool(client: Client[Any], spec: McpTool, request_id: str) -> StructuredTool:
    async def invoke(**arguments: Any) -> tuple[str, AgentArtifact | None]:
        return await _call(client, spec.name, arguments, request_id)

    return StructuredTool.from_function(
        coroutine=invoke,
        name=spec.name,
        description=spec.description or spec.name,
        args_schema=spec.inputSchema,
        response_format="content_and_artifact",
    )


async def build_mcp_tool_registry(client: Client[Any], request_id: str) -> ToolRegistry:
    """Descubre schemas y descripciones autorizados, sin un catálogo estático local."""
    return ToolRegistry(
        adapt_mcp_tool(client, spec, request_id) for spec in await client.list_tools()
    )
