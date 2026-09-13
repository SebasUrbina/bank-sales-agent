import asyncio
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI

from bank_sales_agent.application.use_cases.resolve_principal import ResolvePrincipal
from bank_sales_agent.infrastructure.agent.checkpointer import (
    build_checkpointer,
    close_checkpointer,
)
from bank_sales_agent.infrastructure.agent.runner import LangChainAgentRunner
from bank_sales_agent.infrastructure.agent.runtime import build_agent
from bank_sales_agent.infrastructure.agent.tools.registry import build_tool_registry
from bank_sales_agent.infrastructure.config.settings import Settings
from bank_sales_agent.infrastructure.databricks.client import (
    DatabricksSqlWarehouseClient,
    SqlWarehouseClient,
)
from bank_sales_agent.infrastructure.google_chat.cards import GoogleChatArtifactRenderer
from bank_sales_agent.infrastructure.google_chat.client import (
    GoogleAuthTokenProvider,
    GoogleChatApiClient,
    GoogleChatClient,
    MockGoogleChatClient,
)
from bank_sales_agent.infrastructure.google_chat.publisher import GoogleChatPublisher
from bank_sales_agent.infrastructure.llm.factory import build_chat_model
from bank_sales_agent.infrastructure.mock.repositories import (
    MockEmployeeDirectoryRepository,
    MockSqlWarehouseClient,
)


def create_lifespan(
    settings: Settings,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Construye, conecta y libera la infraestructura del proceso."""
        checkpointer = await asyncio.to_thread(
            build_checkpointer,
            settings.app_env,
            settings.mongodb,
        )

        sql_client: SqlWarehouseClient
        if settings.databricks.enabled:
            assert settings.databricks.server_hostname is not None
            assert settings.databricks.http_path is not None
            assert settings.databricks.access_token is not None
            sql_client = DatabricksSqlWarehouseClient(
                hostname=settings.databricks.server_hostname,
                http_path=settings.databricks.http_path,
                token=settings.databricks.access_token.get_secret_value(),
            )
        else:
            sql_client = MockSqlWarehouseClient()

        google_chat_client: GoogleChatClient
        if settings.google_chat.enabled:
            google_chat_client = GoogleChatApiClient(
                GoogleAuthTokenProvider(),
                timeout_seconds=settings.google_chat.request_timeout_seconds,
            )
        else:
            google_chat_client = MockGoogleChatClient()

        tool_registry = build_tool_registry()
        chat_model = build_chat_model(settings.llm_gateway)
        agent_runner = LangChainAgentRunner(
            build_agent(chat_model, tool_registry, checkpointer),
            sql_client,
        )
        publisher = GoogleChatPublisher(
            google_chat_client,
            GoogleChatArtifactRenderer(),
        )

        # Sólo exponemos a las rutas los componentes que realmente consumen.
        app.state.resolve_principal = ResolvePrincipal(MockEmployeeDirectoryRepository())
        app.state.agent_runner = agent_runner
        app.state.google_chat_publisher = publisher

        try:
            await sql_client.connect()
            await google_chat_client.connect()
            yield
        finally:
            await google_chat_client.close()
            await sql_client.close()
            await asyncio.to_thread(close_checkpointer, checkpointer)

    return lifespan
