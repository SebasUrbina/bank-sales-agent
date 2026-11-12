from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.application.skills import SkillProvider
from app.infrastructure.agent.context import AgentContext
from app.infrastructure.agent.middleware import harness_middlewares
from app.infrastructure.google_chat.client import GoogleChatClient


def build_agent(
    model: BaseChatModel,
    checkpointer: BaseCheckpointSaver[Any],
    skill_provider: SkillProvider,
    chat_client: GoogleChatClient,
) -> Any:
    return create_agent(
        model=model,
        tools=[],
        middleware=harness_middlewares(skill_provider, chat_client),
        context_schema=AgentContext,
        checkpointer=checkpointer,
    )
