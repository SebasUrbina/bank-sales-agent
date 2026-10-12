import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from bank_sales_mcp.main import create_server
from bank_sales_mcp.settings import Settings as ServerSettings
from fastmcp import Client, FastMCP
from fastmcp.client.transports import StreamableHttpTransport

from bank_sales_agent.infrastructure.config.settings import McpSettings
from bank_sales_agent.infrastructure.mcp.client import McpToolGateway


@pytest.fixture
def mcp_server() -> FastMCP:
    return create_server(ServerSettings(signing_secret="test-secret-with-at-least-32-characters"))


@pytest_asyncio.fixture
async def http_gateway(
    monkeypatch: pytest.MonkeyPatch, mcp_server: FastMCP
) -> AsyncIterator[McpToolGateway]:
    secret = "test-secret-with-at-least-32-characters"
    app = mcp_server.http_app()

    def http_client(**kwargs: Any) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), **kwargs)

    def remote_client(url: str, **kwargs: Any) -> Client[Any]:
        return Client(
            StreamableHttpTransport(url, auth=kwargs.pop("auth"), httpx_client_factory=http_client),
            **kwargs,
        )

    monkeypatch.setattr("bank_sales_agent.infrastructure.mcp.client.Client", remote_client)
    started = asyncio.Event()
    stop = asyncio.Event()

    async def serve() -> None:
        async with app.router.lifespan_context(app):
            started.set()
            await stop.wait()

    task = asyncio.create_task(serve())
    await started.wait()
    try:
        yield McpToolGateway(McpSettings(url="http://mcp.test/mcp", signing_secret=secret))
    finally:
        stop.set()
        await task
