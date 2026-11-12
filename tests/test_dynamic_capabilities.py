import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from bank_sales_mcp import catalog as server_catalog
from bank_sales_mcp.catalog import AgentToolSpec, ToolCategory
from bank_sales_mcp.policies import Capability
from conftest import chat_thread
from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from test_skills import write_skill

from app.application.dto import AgentInvocation
from app.domain.models import Principal, Role
from app.infrastructure.agent import runtime
from app.infrastructure.agent.runner import LangChainAgentRunner
from app.infrastructure.google_chat.client import MockGoogleChatClient
from app.infrastructure.google_chat.middleware import CARDS_NOT_SHOWN, CARDS_SHOWN
from app.infrastructure.mcp.client import McpToolGateway
from app.infrastructure.skills.filesystem import FileSkillProvider


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
    return AgentInvocation(thread, Principal(email, Role.COMMERCIAL), text, chat_thread(thread))


@pytest.mark.asyncio
async def test_graph_is_created_once_and_discovers_new_tools_each_invocation(
    http_gateway: McpToolGateway,
    mcp_server: FastMCP,
    monkeypatch: pytest.MonkeyPatch,
    chat_client: MockGoogleChatClient,
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
    runner = LangChainAgentRunner(model, InMemorySaver(), http_gateway, chat_client)
    await runner.run(invocation("ejecutivo@bank.test"))
    assert len(chat_client.sent_messages) == 1
    monkeypatch.setattr(
        server_catalog,
        "TOOL_CATALOG",
        (
            *server_catalog.TOOL_CATALOG,
            AgentToolSpec("new_context", Capability.CUSTOMER_360, ToolCategory.CUSTOMER),
        ),
    )

    @mcp_server.tool(name="new_context")
    async def new_context(topic: str) -> str:
        """Consulta nueva después de crear el agente."""
        return topic

    second = await runner.run(invocation("ejecutivo@bank.test"))
    assert second.text == "Segunda"
    assert len(chat_client.sent_messages) == 1
    assert create.call_count == 1
    assert counter.count == 2  # Cuatro llamadas al modelo, sólo dos tools/list.
    assert "new_context" not in model.seen_tools[0]
    assert "new_context" in model.seen_tools[2]


@pytest.mark.asyncio
async def test_skills_are_progressive_and_share_no_authorization(
    http_gateway: McpToolGateway,
    mcp_server: FastMCP,
    tmp_path: Path,
    chat_client: MockGoogleChatClient,
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
        model, InMemorySaver(), http_gateway, chat_client, FileSkillProvider([tmp_path])
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
async def test_shared_graph_isolates_concurrent_sessions(
    http_gateway: McpToolGateway, chat_client: MockGoogleChatClient
) -> None:
    class RoutingModel(ScriptedModel):
        async def _agenerate(self, messages: Any, **kwargs: Any) -> ChatResult:
            await asyncio.sleep(0)
            latest = messages[-1]
            if isinstance(latest, HumanMessage):
                message = call("customer_360", {"rut": str(latest.content), "render": True})
            else:
                message = AIMessage(content=str(latest.content))
            return ChatResult(generations=[ChatGeneration(message=message)])

    runner = LangChainAgentRunner(
        RoutingModel(responses=[]), InMemorySaver(), http_gateway, chat_client
    )
    first, second = await asyncio.gather(
        runner.run(invocation("ejecutivo@bank.test", "thread-a", "11111111-1")),
        runner.run(invocation("inversiones@bank.test", "thread-b", "22222222-2")),
    )
    assert "Ana Perez" in first.text and "Luis Soto" not in first.text
    assert "Luis Soto" in second.text and "Ana Perez" not in second.text
    cards_by_thread = {
        sent["thread_name"]: sent["body"]["cardsV2"][0]["card"]["header"]["title"]
        for sent in chat_client.sent_messages
    }
    assert cards_by_thread == {
        "spaces/AAAA/threads/thread-a": "Ana Perez",
        "spaces/AAAA/threads/thread-b": "Luis Soto",
    }


@pytest.mark.asyncio
async def test_reserved_skill_tool_name_fails_before_model(
    http_gateway: McpToolGateway,
    mcp_server: FastMCP,
    monkeypatch: pytest.MonkeyPatch,
    chat_client: MockGoogleChatClient,
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
    async def conflicting_tool() -> str:
        """Nombre local reservado."""
        return "conflict"

    model = ScriptedModel(responses=[AIMessage(content="No se debe llamar")])
    runner = LangChainAgentRunner(model, InMemorySaver(), http_gateway, chat_client)
    with pytest.raises(ValueError, match="reservado"):
        await runner.run(invocation("ejecutivo@bank.test"))
    assert model.seen_system == []


@pytest.mark.asyncio
async def test_cards_are_published_when_tool_finishes_and_hidden_from_model(
    http_gateway: McpToolGateway, chat_client: MockGoogleChatClient
) -> None:
    class PublishingModel(ScriptedModel):
        async def _agenerate(self, messages: Any, **kwargs: Any) -> ChatResult:
            sent_before_final_answer.append(len(chat_client.sent_messages))
            return await super()._agenerate(messages, **kwargs)

    sent_before_final_answer: list[int] = []
    model = PublishingModel(
        responses=[
            call("customer_product_offers", {"rut": "11111111-1", "render": True}),
            AIMessage(content="Ana tiene dos ofertas vigentes."),
        ]
    )
    runner = LangChainAgentRunner(model, InMemorySaver(), http_gateway, chat_client)
    result = await runner.run(invocation("ejecutivo@bank.test"))

    assert result.text == "Ana tiene dos ofertas vigentes."
    assert sent_before_final_answer == [0, 1]
    [sent] = chat_client.sent_messages
    assert sent["oauth_token"] is None
    assert sent["thread_name"] == "spaces/AAAA/threads/test-thread"
    assert sent["body"]["cardsV2"][0]["cardId"] == "offers-11111111-1"
    tool_message = next(m for m in model.seen_messages[1] if isinstance(m, ToolMessage))
    assert CARDS_SHOWN in str(tool_message.content)
    assert "cardsV2" not in str(tool_message.content)
    assert tool_message.artifact["cardsV2"]


@pytest.mark.asyncio
async def test_failed_card_publication_is_reported_to_model(http_gateway: McpToolGateway) -> None:
    class FailingChatClient(MockGoogleChatClient):
        async def create_message(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("Google Chat no disponible")

    model = ScriptedModel(
        responses=[
            call("upcoming_maturities", {"render": True}),
            AIMessage(content="Ana tiene un depósito por vencer."),
        ]
    )
    runner = LangChainAgentRunner(model, InMemorySaver(), http_gateway, FailingChatClient())
    result = await runner.run(invocation("ejecutivo@bank.test"))

    assert result.text == "Ana tiene un depósito por vencer."
    tool_message = next(m for m in model.seen_messages[1] if isinstance(m, ToolMessage))
    assert tool_message.status == "success"
    assert CARDS_NOT_SHOWN in str(tool_message.content)
