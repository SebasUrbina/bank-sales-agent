from typing import Any

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.base import BaseCheckpointSaver

from bank_sales_agent.infrastructure.agent.context import AgentContext
from bank_sales_agent.infrastructure.agent.middleware import harness_middlewares
from bank_sales_agent.infrastructure.agent.tools.registry import ToolRegistry
from bank_sales_agent.infrastructure.config.settings import LangChainSettings


def build_agent(
    settings: LangChainSettings,
    registry: ToolRegistry,
    checkpointer: BaseCheckpointSaver[Any],
) -> Any:
    chat_model = (
        init_chat_model(
            settings.model_name,
            api_key=settings.openai_api_key.get_secret_value(),
        )
        if settings.openai_api_key
        else settings.model_name
    )
    return create_agent(
        model=chat_model,
        tools=registry.all(),
        middleware=harness_middlewares(registry),
        context_schema=AgentContext,
        checkpointer=checkpointer,
    )
