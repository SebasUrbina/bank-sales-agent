"""Descubrimiento por invocación y despacho dinámico en un grafo compartido."""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
    ToolCallRequest,
)
from langchain.messages import SystemMessage
from langgraph.runtime import Runtime

from bank_sales_agent.application.skills import SkillProvider
from bank_sales_agent.domain.errors import ForbiddenError
from bank_sales_agent.infrastructure.agent.context import AgentContext
from bank_sales_agent.infrastructure.agent.tools.registry import ToolRegistry
from bank_sales_agent.infrastructure.mcp.tools import build_mcp_tool_registry
from bank_sales_agent.infrastructure.skills.tools import skill_catalog_prompt, skill_tools


class DynamicCapabilitiesMiddleware(AgentMiddleware[AgentState, AgentContext]):
    def __init__(self, skill_provider: SkillProvider) -> None:
        super().__init__()
        self._skill_provider = skill_provider

    async def abefore_agent(self, state: AgentState, runtime: Runtime[AgentContext]) -> None:
        context = runtime.context
        if context.mcp_client is None:
            raise RuntimeError("Cliente MCP conectado es obligatorio")
        registry = await build_mcp_tool_registry(context.mcp_client, context.request_id)
        skills = await self._skill_provider.discover()
        # Reservamos nombres locales incluso sin skills para evitar colisiones futuras.
        if {tool.name for tool in registry.all()} & {"load_skill", "read_skill_resource"}:
            raise ValueError("Tool MCP usa un nombre reservado para skills")
        context.capabilities.registry = ToolRegistry([*registry.all(), *skill_tools(skills)])
        context.capabilities.skill_prompt = skill_catalog_prompt(skills)

    async def awrap_model_call(
        self,
        request: ModelRequest[AgentContext],
        handler: Callable[[ModelRequest[AgentContext]], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        capabilities = request.runtime.context.capabilities
        if capabilities.registry is None:
            raise RuntimeError("Las capacidades deben descubrirse antes de ejecutar el modelo")
        overrides: dict[str, Any] = {"tools": capabilities.registry.all()}
        if capabilities.skill_prompt:
            content = request.system_message.content if request.system_message else ""
            overrides["system_message"] = SystemMessage(
                content=f"{content}\n\n{capabilities.skill_prompt}"
            )
        return await handler(request.override(**overrides))

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[Any]],
    ) -> Any:
        context = request.runtime.context
        if not isinstance(context, AgentContext):
            raise RuntimeError("AgentContext es obligatorio")
        registry = context.capabilities.registry
        tool = registry.get(request.tool_call["name"]) if registry else None
        if tool is None:
            raise ForbiddenError("Tool no disponible en esta invocación")
        return await handler(request.override(tool=tool))
