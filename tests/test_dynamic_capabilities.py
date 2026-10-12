import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from bank_sales_mcp import catalog as server_catalog
from bank_sales_mcp.catalog import AgentToolSpec, ToolCategory
from bank_sales_mcp.policies import Capability
from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from test_skills import write_skill

from bank_sales_agent.application.dto import AgentInvocation
from bank_sales_agent.domain.models import Principal, Role
from bank_sales_agent.infrastructure.agent import runtime
from bank_sales_agent.infrastructure.agent.runner import LangChainAgentRunner
from bank_sales_agent.infrastructure.mcp.client import McpToolGateway
from bank_sales_agent.infrastructure.mcp.contracts import ToolResponse
from bank_sales_agent.infrastructure.skills.filesystem import FileSkillProvider


class ScriptedModel(FakeMessagesListChatModel):
    seen_tools: list[set[str]] = []
    seen_system: list[str] = []
    seen_messages: list[list[Any]] = []

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedModel":
        self.seen_tools.append({tool.name for tool in tools})
        return self

    async def _agenerate(self, messages: Any, **kwargs: Any) -> ChatResult:
        self.seen_system.append(str(messages[0].content))
        self.seen_messages.append(list(messages))
        return self._generate(messages, **kwargs)


class CountLists(Middleware):
    def __init__(self) -> None:
        self.count = 0

    async def on_list_tools(self, context: Any, call_next: Any) -> Any:
        self.count += 1
        return await call_next(context)


def call(name: str, args: dict[str, Any]) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": name}])


def invocation(email: str, thread: str = "test-thread", text: str = "Ayúdame") -> AgentInvocation:
    return AgentInvocation(thread, Principal(email, Role.COMMERCIAL), text, thread)


@pytest.mark.asyncio
async def test_graph_is_created_once_and_discovers_new_tools_each_invocation(
    http_gateway: McpToolGateway, mcp_server: FastMCP, monkeypatch: pytest.MonkeyPatch
) -> None:
    create = Mock(wraps=runtime.create_agent)
    monkeypatch.setattr(runtime, "create_agent", create)
    counter = CountLists()
    mcp_server.add_middleware(counter)
    model = ScriptedModel(
        responses=[
            call("customer_360", {"rut": "11111111-1", "render": True}),
            AIMessage(content="Primera"),
            call("new_context", {"topic": "x"}),
            AIMessage(content="Segunda"),
        ]
    )
    runner = LangChainAgentRunner(model, InMemorySaver(), http_gateway)
    first = await runner.run(invocation("ejecutivo@bank.test"))
    assert first.artifacts
    monkeypatch.setattr(
        server_catalog,
        "TOOL_CATALOG",
        (
            *server_catalog.TOOL_CATALOG,
            AgentToolSpec("new_context", Capability.CUSTOMER_360, ToolCategory.CUSTOMER),
        ),
    )

    @mcp_server.tool(name="new_context")
    async def new_context(topic: str) -> ToolResponse:
        """Consulta nueva después de crear el agente."""
        return ToolResponse(context=topic)

    second = await runner.run(invocation("ejecutivo@bank.test"))
    assert second.text == "Segunda"
    assert second.artifacts == ()
    assert create.call_count == 1
    assert counter.count == 2  # Cuatro llamadas al modelo, sólo dos tools/list.
    assert "new_context" not in model.seen_tools[0]
    assert "new_context" in model.seen_tools[2]


@pytest.mark.asyncio
async def test_skills_are_progressive_and_share_no_authorization(
    http_gateway: McpToolGateway, mcp_server: FastMCP, tmp_path: Path
) -> None:
    directory = write_skill(tmp_path, body="SECRET_INSTRUCTIONS: consultar referencia outline.md")
    (directory / "outline.md").write_text("REFERENCE_CONTENT")
    counter = CountLists()
    mcp_server.add_middleware(counter)
    model = ScriptedModel(
        responses=[
            call("load_skill", {"name": "meeting"}),
            call("read_skill_resource", {"name": "meeting", "path": "outline.md"}),
            call("list_prioritized_customers", {}),
            AIMessage(content="Preparación limitada a las tools disponibles"),
        ]
    )
    runner = LangChainAgentRunner(
        model, InMemorySaver(), http_gateway, FileSkillProvider([tmp_path])
    )
    result = await runner.run(invocation("servicio@bank.test"))
    assert result.text
    assert counter.count == 1
    assert "Preparar una reunión" in model.seen_system[0]
    assert "SECRET_INSTRUCTIONS" not in model.seen_system[0]
    assert "load_skill" in model.seen_tools[0]
    assert "list_prioritized_customers" not in model.seen_tools[0]
    assert any(
        isinstance(m, ToolMessage) and "SECRET_INSTRUCTIONS" in str(m.content)
        for m in model.seen_messages[1]
    )
    assert any(
        isinstance(m, ToolMessage) and "REFERENCE_CONTENT" in str(m.content)
        for m in model.seen_messages[2]
    )
    assert any(isinstance(m, ToolMessage) and m.status == "error" for m in model.seen_messages[3])


@pytest.mark.asyncio
async def test_shared_graph_isolates_concurrent_sessions(http_gateway: McpToolGateway) -> None:
    class RoutingModel(ScriptedModel):
        async def _agenerate(self, messages: Any, **kwargs: Any) -> ChatResult:
            await asyncio.sleep(0)
            latest = messages[-1]
            if isinstance(latest, HumanMessage):
                message = call("customer_360", {"rut": str(latest.content), "render": True})
            else:
                message = AIMessage(content=str(latest.content))
            return ChatResult(generations=[ChatGeneration(message=message)])

    runner = LangChainAgentRunner(RoutingModel(responses=[]), InMemorySaver(), http_gateway)
    first, second = await asyncio.gather(
        runner.run(invocation("ejecutivo@bank.test", "thread-a", "11111111-1")),
        runner.run(invocation("inversiones@bank.test", "thread-b", "22222222-2")),
    )
    assert "Ana Perez" in first.text and "Luis Soto" not in first.text
    assert "Luis Soto" in second.text and "Ana Perez" not in second.text
    assert first.artifacts and second.artifacts


@pytest.mark.asyncio
async def test_reserved_skill_tool_name_fails_before_model(
    http_gateway: McpToolGateway, mcp_server: FastMCP, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        server_catalog,
        "TOOL_CATALOG",
        (
            *server_catalog.TOOL_CATALOG,
            AgentToolSpec("load_skill", Capability.CUSTOMER_360, ToolCategory.CUSTOMER),
        ),
    )

    @mcp_server.tool(name="load_skill")
    async def conflicting_tool() -> ToolResponse:
        """Nombre local reservado."""
        return ToolResponse(context="conflict")

    model = ScriptedModel(responses=[AIMessage(content="No se debe llamar")])
    runner = LangChainAgentRunner(model, InMemorySaver(), http_gateway)
    with pytest.raises(ValueError, match="reservado"):
        await runner.run(invocation("ejecutivo@bank.test"))
    assert model.seen_system == []
