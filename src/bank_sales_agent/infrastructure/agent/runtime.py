from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver

from bank_sales_agent.application.skills import SkillProvider
from bank_sales_agent.infrastructure.agent.context import AgentContext
from bank_sales_agent.infrastructure.agent.middleware import harness_middlewares


def build_agent(
    model: BaseChatModel,
    checkpointer: BaseCheckpointSaver[Any],
    skill_provider: SkillProvider,
) -> Any:
    return create_agent(
        model=model,
        tools=[],
        middleware=harness_middlewares(skill_provider),
        context_schema=AgentContext,
        checkpointer=checkpointer,
    )
