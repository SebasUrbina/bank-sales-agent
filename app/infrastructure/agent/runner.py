from typing import Any

from fastmcp import Client
from langchain.messages import AIMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages.base import BaseMessage
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.application.dto import AgentInvocation, AgentResult
from app.application.skills import SkillProvider
from app.infrastructure.agent.context import AgentContext
from app.infrastructure.agent.runtime import build_agent
from app.infrastructure.google_chat.client import GoogleChatClient
from app.infrastructure.mcp.client import McpToolGateway
from app.infrastructure.skills.filesystem import FileSkillProvider


def _last_text(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return str(message.content)
    return "No fue posible generar una respuesta."


class LangChainAgentRunner:
    def __init__(
        self,
        model: BaseChatModel,
        checkpointer: BaseCheckpointSaver[Any],
        mcp_gateway: McpToolGateway,
        chat_client: GoogleChatClient,
        skill_provider: SkillProvider | None = None,
    ) -> None:
        self._agent = build_agent(
            model, checkpointer, skill_provider or FileSkillProvider([]), chat_client
        )
        self._mcp_gateway = mcp_gateway

    async def run(self, invocation: AgentInvocation) -> AgentResult:
        async with self._mcp_gateway.connect(invocation.principal) as client:
            return await self._run(invocation, client)

    async def _run(self, invocation: AgentInvocation, client: Client[Any]) -> AgentResult:
        result = await self._agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": invocation.message,
                    },
                ]
            },
            context=AgentContext(
                principal=invocation.principal,
                request_id=invocation.request_id,
                chat=invocation.chat,
                mcp_client=client,
            ),
            config={
                "configurable": {
                    "thread_id": invocation.thread_id,
                },
            },
        )
        messages: list[BaseMessage] = result["messages"]
        return AgentResult(text=_last_text(messages))
