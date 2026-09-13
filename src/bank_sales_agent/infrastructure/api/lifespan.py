import asyncio
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI

from bank_sales_agent.application.ports import CustomerInsightsRepository
from bank_sales_agent.application.use_cases.customer_360 import GetCustomer360
from bank_sales_agent.application.use_cases.list_customers import ListPrioritizedCustomers
from bank_sales_agent.application.use_cases.resolve_principal import ResolvePrincipal
from bank_sales_agent.infrastructure.agent.checkpointer import (
    build_checkpointer,
    close_checkpointer,
)
from bank_sales_agent.infrastructure.agent.runner import LangChainAgentRunner
from bank_sales_agent.infrastructure.agent.runtime import build_agent
from bank_sales_agent.infrastructure.agent.tools.registry import build_tool_registry
from bank_sales_agent.infrastructure.config.settings import Settings
from bank_sales_agent.infrastructure.databricks.client import DatabricksSqlWarehouseClient
from bank_sales_agent.infrastructure.databricks.repositories import (
    DatabricksCustomerInsightsRepository,
)
from bank_sales_agent.infrastructure.google_chat.cards import GoogleChatArtifactRenderer
from bank_sales_agent.infrastructure.google_chat.client import (
    GoogleAuthTokenProvider,
    GoogleChatApiClient,
    GoogleChatClient,
    MockGoogleChatClient,
)
from bank_sales_agent.infrastructure.google_chat.publisher import GoogleChatPublisher
from bank_sales_agent.infrastructure.mock.repositories import (
    MockCustomerInsightsRepository,
    MockEmployeeDirectoryRepository,
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

        databricks_client: DatabricksSqlWarehouseClient | None = None
        repository: CustomerInsightsRepository
        if settings.databricks.enabled:
            assert settings.databricks.server_hostname is not None
            assert settings.databricks.http_path is not None
            assert settings.databricks.access_token is not None
            databricks_client = DatabricksSqlWarehouseClient(
                hostname=settings.databricks.server_hostname,
                http_path=settings.databricks.http_path,
                token=settings.databricks.access_token.get_secret_value(),
            )
            repository = DatabricksCustomerInsightsRepository(databricks_client)
        else:
            repository = MockCustomerInsightsRepository()

        google_chat_client: GoogleChatClient
        if settings.google_chat.enabled:
            google_chat_client = GoogleChatApiClient(
                GoogleAuthTokenProvider(),
                timeout_seconds=settings.google_chat.request_timeout_seconds,
            )
        else:
            google_chat_client = MockGoogleChatClient()

        get_customer_360 = GetCustomer360(repository)
        list_customers = ListPrioritizedCustomers(repository)
        tool_registry = build_tool_registry(get_customer_360, list_customers)
        agent_runner = LangChainAgentRunner(
            build_agent(settings.langchain, tool_registry, checkpointer)
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
            if databricks_client is not None:
                await databricks_client.connect()
            await google_chat_client.connect()
            yield
        finally:
            await google_chat_client.close()
            if databricks_client is not None:
                await databricks_client.close()
            await asyncio.to_thread(close_checkpointer, checkpointer)

    return lifespan
