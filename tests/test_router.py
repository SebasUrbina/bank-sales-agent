from typing import Any

import httpx
import pytest

from app.application.dto import AgentInvocation, AgentResult
from app.application.use_cases.resolve_principal import ResolvePrincipal
from app.infrastructure.api.app import create_app
from app.infrastructure.api.router import get_agent_runner, get_publisher, get_resolve_principal
from app.infrastructure.google_chat.client import MockGoogleChatClient
from app.infrastructure.google_chat.publisher import GoogleChatPublisher
from app.infrastructure.mock.repositories import MockEmployeeDirectoryRepository
from app.settings import Settings

PAYLOAD: dict[str, Any] = {
    "message": "Dame mi lista de clientes prioritarios",
    "space_name": "spaces/AAAA",
    "thread_name": "spaces/AAAA/threads/BBBB",
    "user_email": "ejecutivo@bank.test",
    "user_oauth_token": "user-oauth-token",
}


class EchoRunner:
    def __init__(self) -> None:
        self.invocations: list[AgentInvocation] = []

    async def run(self, invocation: AgentInvocation) -> AgentResult:
        self.invocations.append(invocation)
        return AgentResult(f"Recibido: {invocation.message}")


@pytest.fixture
def chat_client() -> MockGoogleChatClient:
    return MockGoogleChatClient()


@pytest.fixture
def runner() -> EchoRunner:
    return EchoRunner()


@pytest.fixture
def client(runner: EchoRunner, chat_client: MockGoogleChatClient) -> httpx.AsyncClient:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_resolve_principal] = lambda: ResolvePrincipal(
        MockEmployeeDirectoryRepository()
    )
    app.dependency_overrides[get_agent_runner] = lambda: runner
    app.dependency_overrides[get_publisher] = lambda: GoogleChatPublisher(chat_client)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://api.test")


@pytest.mark.asyncio
async def test_health(client: httpx.AsyncClient) -> None:
    async with client:
        response = await client.get("/health")
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_invoke_accepts_and_publishes_in_background(
    client: httpx.AsyncClient, runner: EchoRunner, chat_client: MockGoogleChatClient
) -> None:
    async with client:
        response = await client.post("/v1/agent/invoke", json=PAYLOAD)

    assert response.status_code == 202
    request_id = response.json()["request_id"]
    [invocation] = runner.invocations
    assert invocation.request_id == request_id
    assert invocation.thread_id == "spaces/AAAA/threads/BBBB"
    [sent] = chat_client.sent_messages
    assert sent["body"] == {"text": "Recibido: Dame mi lista de clientes prioritarios"}
    assert sent["request_id"] == request_id


@pytest.mark.asyncio
async def test_invoke_rejects_unknown_user(client: httpx.AsyncClient, runner: EchoRunner) -> None:
    async with client:
        response = await client.post(
            "/v1/agent/invoke", json={**PAYLOAD, "user_email": "unknown@bank.test"}
        )

    assert response.status_code == 403
    assert runner.invocations == []
