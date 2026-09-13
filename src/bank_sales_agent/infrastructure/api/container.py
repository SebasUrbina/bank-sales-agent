from dataclasses import dataclass

from pydantic_settings import BaseSettings, SettingsConfigDict

from bank_sales_agent.application.use_cases.customer_360 import GetCustomer360
from bank_sales_agent.application.use_cases.list_customers import ListPrioritizedCustomers
from bank_sales_agent.application.use_cases.process_agent_request import ProcessAgentRequest
from bank_sales_agent.application.use_cases.resolve_principal import ResolvePrincipal
from bank_sales_agent.infrastructure.agent.runner import LangChainAgentRunner
from bank_sales_agent.infrastructure.agent.runtime import build_agent
from bank_sales_agent.infrastructure.agent.tools.registry import build_tool_registry
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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "local"
    model_name: str = "openai:gpt-5-mini"
    google_chat_enabled: bool = False


@dataclass
class Container:
    agent_runner: LangChainAgentRunner
    resolve_principal: ResolvePrincipal
    process_agent_request: ProcessAgentRequest
    google_chat_client: GoogleChatClient

    async def connect(self) -> None:
        await self.google_chat_client.connect()

    async def close(self) -> None:
        await self.google_chat_client.close()


def build_container(settings: Settings | None = None) -> Container:
    config = settings or Settings()
    directory = MockEmployeeDirectoryRepository()
    repository = MockCustomerInsightsRepository()
    get_360 = GetCustomer360(repository)
    list_customers = ListPrioritizedCustomers(repository)
    registry = build_tool_registry(get_360, list_customers)
    agent = build_agent(config.model_name, registry)
    runner = LangChainAgentRunner(agent)
    chat_client: GoogleChatClient
    if config.google_chat_enabled:
        chat_client = GoogleChatApiClient(GoogleAuthTokenProvider())
    else:
        chat_client = MockGoogleChatClient()
    publisher = GoogleChatPublisher(chat_client, GoogleChatArtifactRenderer())
    return Container(
        agent_runner=runner,
        resolve_principal=ResolvePrincipal(directory),
        process_agent_request=ProcessAgentRequest(runner, publisher),
        google_chat_client=chat_client,
    )
