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
from bank_sales_agent.infrastructure.config.settings import Settings
from bank_sales_agent.infrastructure.google_chat.cards import GoogleChatArtifactRenderer
from bank_sales_agent.infrastructure.google_chat.client import (
    GoogleAuthTokenProvider,
    GoogleChatApiClient,
    GoogleChatClient,
    MockGoogleChatClient,
)
from bank_sales_agent.infrastructure.google_chat.publisher import GoogleChatPublisher
from bank_sales_agent.infrastructure.llm.factory import build_chat_model
from bank_sales_agent.infrastructure.mcp.client import McpToolGateway
from bank_sales_agent.infrastructure.mock.repositories import (
    MockEmployeeDirectoryRepository,
)
from bank_sales_agent.infrastructure.skills.filesystem import FileSkillProvider


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

        google_chat_client: GoogleChatClient
        if settings.google_chat.enabled:
            google_chat_client = GoogleChatApiClient(
                GoogleAuthTokenProvider(),
                timeout_seconds=settings.google_chat.request_timeout_seconds,
            )
        else:
            google_chat_client = MockGoogleChatClient()

        chat_model = build_chat_model(settings.llm_gateway)
        agent_runner = LangChainAgentRunner(
            chat_model,
            checkpointer,
            McpToolGateway(settings.mcp),
            FileSkillProvider(
                settings.agent_skills.directories, settings.agent_skills.max_file_bytes
            ),
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
            await google_chat_client.connect()
            yield
        finally:
            await google_chat_client.close()
            await asyncio.to_thread(close_checkpointer, checkpointer)

    return lifespan
