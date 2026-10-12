from typing import Any

from fastmcp import Client
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages.base import BaseMessage
from langgraph.checkpoint.base import BaseCheckpointSaver

from bank_sales_agent.application.artifacts import AgentArtifact
from bank_sales_agent.application.dto import AgentInvocation, AgentResult
from bank_sales_agent.application.skills import SkillProvider
from bank_sales_agent.infrastructure.agent.context import AgentContext
from bank_sales_agent.infrastructure.agent.runtime import build_agent
from bank_sales_agent.infrastructure.mcp.client import McpToolGateway
from bank_sales_agent.infrastructure.skills.filesystem import FileSkillProvider


def _last_text(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return str(message.content)
    return "No fue posible generar una respuesta."


def collect_artifacts(messages: list[BaseMessage]) -> tuple[AgentArtifact, ...]:
    # Los checkpoints incluyen turnos anteriores: no volver a publicar sus cards.
    start = next(
        (i + 1 for i in range(len(messages) - 1, -1, -1) if isinstance(messages[i], HumanMessage)),
        0,
    )
    return tuple(
        message.artifact
        for message in messages[start:]
        if isinstance(message, ToolMessage) and message.artifact is not None
    )


class LangChainAgentRunner:
    def __init__(
        self,
        model: BaseChatModel,
        checkpointer: BaseCheckpointSaver[Any],
        mcp_gateway: McpToolGateway,
        skill_provider: SkillProvider | None = None,
    ) -> None:
        self._agent = build_agent(model, checkpointer, skill_provider or FileSkillProvider([]))
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
                mcp_client=client,
            ),
            config={
                "configurable": {
                    "thread_id": invocation.thread_id,
                },
            },
        )
        messages: list[BaseMessage] = result["messages"]
        return AgentResult(
            text=_last_text(messages),
            artifacts=collect_artifacts(messages),
        )
