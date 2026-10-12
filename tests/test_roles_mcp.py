import json
from typing import Any

import httpx
import jwt
import pytest
from bank_sales_mcp.catalog import visible_tool_names
from bank_sales_mcp.main import create_server
from bank_sales_mcp.settings import Settings as ServerSettings
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import ValidationError

from bank_sales_agent.application.dto import AgentResult
from bank_sales_agent.domain.errors import CustomerNotFoundError, ForbiddenError
from bank_sales_agent.domain.models import Principal, Role
from bank_sales_agent.infrastructure.agent.runner import collect_artifacts
from bank_sales_agent.infrastructure.config.settings import McpSettings, Settings
from bank_sales_agent.infrastructure.google_chat.cards import GoogleChatArtifactRenderer
from bank_sales_agent.infrastructure.mcp.client import McpToolGateway, issue_token
from bank_sales_agent.infrastructure.mcp.contracts import ToolResponse
from bank_sales_agent.infrastructure.mcp.tools import build_mcp_tool_registry
from bank_sales_agent.infrastructure.mock.repositories import EXECUTIVE_ONE


@pytest.mark.parametrize(
    ("label", "role"),
    [
        ("ejecutivo comercial", Role.COMMERCIAL),
        ("ejecutivo inversiones asesor", Role.INVESTMENTS_ADVISOR),
        (" ejecutivo inversiones  no asesor ", Role.INVESTMENTS_NON_ADVISOR),
        ("ejecutivo integral", Role.INTEGRAL),
        ("ejecutivo centro servicio", Role.SERVICE_CENTER),
        ("gerente", Role.MANAGER),
        ("admin", Role.ADMIN),
        ("investments", Role.INVESTMENTS_ADVISOR),
        ("leader", Role.MANAGER),
    ],
)
def test_role_labels_and_legacy_values(label: str, role: Role) -> None:
    assert Role(label) is role
    assert len(Role) == 7


def test_unknown_role_and_incomplete_http_config_fail_closed() -> None:
    with pytest.raises(ValueError):
        Role("supervisor")
    with pytest.raises(ValueError):
        McpToolGateway(McpSettings())
    with pytest.raises(ValidationError):
        McpSettings(url="http://localhost:8001/mcp", signing_secret="short")


@pytest.mark.asyncio
@pytest.mark.parametrize("role", list(Role))
async def test_mcp_filters_catalog_and_protects_call_for_every_role(
    role: Role, http_gateway: McpToolGateway
) -> None:
    emails = {
        Role.COMMERCIAL: EXECUTIVE_ONE,
        Role.INTEGRAL: "integral@bank.test",
        Role.INVESTMENTS_ADVISOR: "inversiones@bank.test",
        Role.INVESTMENTS_NON_ADVISOR: "inversiones-no-asesor@bank.test",
        Role.SERVICE_CENTER: "servicio@bank.test",
        Role.MANAGER: "gerente@bank.test",
        Role.ADMIN: "admin@bank.test",
    }
    principal = Principal(emails[role], role)
    gateway = http_gateway
    async with gateway.connect(principal) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == visible_tool_names(principal)
        for tool in tools:
            assert not {"role", "principal", "requester_email", "runtime"} & set(
                tool.inputSchema["properties"]
            )
        if role is Role.SERVICE_CENTER:
            result = await client.call_tool("list_prioritized_customers", {}, raise_on_error=False)
            assert result.is_error
            assert json.loads(result.content[0].text)["error"]["code"] == "access_denied"


@pytest.mark.asyncio
async def test_context_only_and_artifact_round_trip_to_cards_v2(
    http_gateway: McpToolGateway,
) -> None:
    principal = Principal(EXECUTIVE_ONE, Role.COMMERCIAL)
    async with http_gateway.connect(principal) as client:
        registry = await build_mcp_tool_registry(client, "request-1")
        tools = {tool.name: tool for tool in registry.all()}
        customer_360 = tools["customer_360"]
        list_prioritized_customers = tools["list_prioritized_customers"]
        assert customer_360.coroutine is not None
        text, artifact = await customer_360.coroutine(rut="11111111-1")
        assert json.loads(text)["full_name"] == "Ana Perez"
        assert artifact is None
        text, artifact = await customer_360.coroutine(rut="11111111-1", render=True)
        assert artifact is not None
        payload = GoogleChatArtifactRenderer().render(AgentResult(text=text, artifacts=(artifact,)))
        assert payload.build()["cardsV2"][0]["card"]["header"]["title"] == "Ana Perez"
        assert list_prioritized_customers.coroutine is not None
        with pytest.raises(ForbiddenError):
            await list_prioritized_customers.coroutine(executive_email="inversiones@bank.test")
        with pytest.raises(CustomerNotFoundError):
            await customer_360.coroutine(rut="22222222-2")


@pytest.mark.asyncio
async def test_mcp_validates_limits_and_empty_portfolio_card(http_gateway: McpToolGateway) -> None:
    principal = Principal("integral@bank.test", Role.INTEGRAL)
    async with http_gateway.connect(principal) as client:
        invalid = await client.call_tool(
            "list_prioritized_customers", {"limit": 101}, raise_on_error=False
        )
        assert invalid.is_error
        result = await client.call_tool("list_prioritized_customers", {"render": True})
        text, artifact = ToolResponse.model_validate(result.structured_content).to_result()
        assert json.loads(text) == []
        assert artifact is not None
        assert (
            GoogleChatArtifactRenderer()
            .render(AgentResult(text="Sin clientes", artifacts=(artifact,)))
            .build()["cardsV2"]
        )


@pytest.mark.asyncio
async def test_mcp_sessions_do_not_share_identity(http_gateway: McpToolGateway) -> None:
    import asyncio

    async def query(principal: Principal) -> set[str]:
        async with http_gateway.connect(principal) as client:
            result = await client.call_tool("list_prioritized_customers", {})
            text, _ = ToolResponse.model_validate(result.structured_content).to_result()
            return {row["executive_email"] for row in json.loads(text)}

    results = await asyncio.gather(
        query(Principal(EXECUTIVE_ONE, Role.COMMERCIAL)),
        query(Principal("inversiones@bank.test", Role.INVESTMENTS_NON_ADVISOR)),
    )
    assert results == [{EXECUTIVE_ONE}, {"inversiones@bank.test"}]


@pytest.mark.asyncio
async def test_http_mcp_uses_signed_identity_and_server_directory() -> None:
    settings = Settings(
        mcp={
            "url": "http://mcp.test/mcp",
            "signing_secret": "test-secret-with-at-least-32-characters",
        }
    )
    server = create_server(ServerSettings(signing_secret=settings.mcp.signing_secret))
    app = server.http_app()

    def http_client(**kwargs: Any) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), **kwargs)

    async with app.router.lifespan_context(app):
        token = issue_token(Principal("servicio@bank.test", Role.ADMIN), settings.mcp)
        async with Client(
            StreamableHttpTransport(
                str(settings.mcp.url), auth=token, httpx_client_factory=http_client
            )
        ) as client:
            assert {tool.name for tool in await client.list_tools()} == {"customer_360"}
            result = await client.call_tool("list_prioritized_customers", {}, raise_on_error=False)
            assert result.is_error
        # La firma, expiración y audiencia se validan antes de acceder a MCP.
        claims = jwt.decode(token, options={"verify_signature": False})
        for invalid in (
            token + "broken",
            jwt.encode(
                {**claims, "exp": 1}, settings.mcp.signing_secret.get_secret_value(), "HS256"
            ),
            jwt.encode(
                {**claims, "aud": "other"}, settings.mcp.signing_secret.get_secret_value(), "HS256"
            ),
        ):
            async with http_client() as client:
                response = await client.post(
                    str(settings.mcp.url), headers={"Authorization": f"Bearer {invalid}"}, json={}
                )
                assert response.status_code == 401


def test_previous_turn_artifacts_are_not_republished() -> None:
    marker = object()
    messages = [
        ToolMessage(content="previous", tool_call_id="old", artifact=marker),
        HumanMessage(content="Nueva pregunta"),
        AIMessage(content="Nueva respuesta"),
    ]
    assert collect_artifacts(messages) == ()


@pytest.mark.asyncio
async def test_agent_runs_tool_calls_through_mcp_and_preserves_artifacts(
    http_gateway: McpToolGateway,
) -> None:
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langgraph.checkpoint.memory import InMemorySaver

    from bank_sales_agent.application.dto import AgentInvocation
    from bank_sales_agent.infrastructure.agent.runner import LangChainAgentRunner

    class ScriptedModel(FakeMessagesListChatModel):
        def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedModel":
            return self

    model = ScriptedModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "customer_360",
                        "args": {"rut": "11111111-1", "render": True},
                        "id": "customer-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Ana tiene un saldo de $24.500.000."),
        ]
    )
    runner = LangChainAgentRunner(model, InMemorySaver(), http_gateway)
    result = await runner.run(
        AgentInvocation(
            request_id="agent-mcp-test",
            principal=Principal(EXECUTIVE_ONE, Role.COMMERCIAL),
            message="Dame la vista 360 con tarjeta",
            thread_id="mcp-test-thread",
        )
    )
    assert result.text == "Ana tiene un saldo de $24.500.000."
    assert len(result.artifacts) == 1
    assert GoogleChatArtifactRenderer().render(result).build()["cardsV2"]


@pytest.mark.asyncio
async def test_mcp_role_wins_over_stale_role_in_agent(http_gateway: McpToolGateway) -> None:
    # La API cree que es admin; el directorio MCP lo identifica como centro de servicio.
    async with http_gateway.connect(Principal("servicio@bank.test", Role.ADMIN)) as client:
        registry = await build_mcp_tool_registry(client, "stale-role")
        assert {tool.name for tool in registry.all()} == {"customer_360"}
        result = await client.call_tool("list_prioritized_customers", {}, raise_on_error=False)
        assert result.is_error


@pytest.mark.asyncio
async def test_permission_changes_in_mcp_need_no_agent_catalog_update(
    http_gateway: McpToolGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bank_sales_mcp.policies import ROLE_CAPABILITIES, Capability

    monkeypatch.setitem(ROLE_CAPABILITIES, Role.COMMERCIAL, frozenset({Capability.CUSTOMER_360}))
    async with http_gateway.connect(Principal(EXECUTIVE_ONE, Role.COMMERCIAL)) as client:
        registry = await build_mcp_tool_registry(client, "changed-policy")
        assert {tool.name for tool in registry.all()} == {"customer_360"}
        result = await client.call_tool("list_prioritized_customers", {}, raise_on_error=False)
        assert result.is_error


@pytest.mark.asyncio
async def test_new_mcp_tool_is_discovered_with_its_schema_and_description(
    http_gateway: McpToolGateway, mcp_server: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bank_sales_mcp import catalog
    from bank_sales_mcp.catalog import AgentToolSpec, ToolCategory
    from bank_sales_mcp.policies import Capability

    monkeypatch.setattr(
        catalog,
        "TOOL_CATALOG",
        (
            *catalog.TOOL_CATALOG,
            AgentToolSpec("new_customer_context", Capability.CUSTOMER_360, ToolCategory.CUSTOMER),
        ),
    )

    @mcp_server.tool(name="new_customer_context")
    async def new_context(topic: str) -> ToolResponse:
        """Nueva consulta publicada únicamente en el MCP."""
        return ToolResponse(context=f"Contexto nuevo: {topic}")

    async with http_gateway.connect(Principal(EXECUTIVE_ONE, Role.COMMERCIAL)) as client:
        registry = await build_mcp_tool_registry(client, "new-tool")
        data_tool = next(tool for tool in registry.all() if tool.name == "new_customer_context")
        assert "únicamente en el MCP" in data_tool.description
        assert data_tool.args["topic"]["type"] == "string"
        message = await data_tool.ainvoke(
            {
                "name": data_tool.name,
                "args": {"topic": "cartera"},
                "id": "new-call",
                "type": "tool_call",
            }
        )
        assert message.content == "Contexto nuevo: cartera"
        assert message.artifact is None


@pytest.mark.asyncio
async def test_mcp_can_revoke_permissions_after_discovery(
    http_gateway: McpToolGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bank_sales_mcp.policies import ROLE_CAPABILITIES

    async with http_gateway.connect(Principal(EXECUTIVE_ONE, Role.COMMERCIAL)) as client:
        registry = await build_mcp_tool_registry(client, "revoked-policy")
        data_tool = next(tool for tool in registry.all() if tool.name == "customer_360")
        monkeypatch.setitem(ROLE_CAPABILITIES, Role.COMMERCIAL, frozenset())
        assert (await build_mcp_tool_registry(client, "no-permissions")).all() == []
        with pytest.raises(ForbiddenError):
            await data_tool.ainvoke({"rut": "11111111-1"})
