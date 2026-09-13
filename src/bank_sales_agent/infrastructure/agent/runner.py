from typing import Any

from langchain.messages import AIMessage, ToolMessage
from langchain_core.messages.base import BaseMessage

from bank_sales_agent.application.artifacts import AgentArtifact
from bank_sales_agent.application.dto import AgentInvocation, AgentResult
from bank_sales_agent.infrastructure.agent.context import AgentContext
from bank_sales_agent.infrastructure.databricks.client import (
    ScopedSqlWarehouseClient,
    SqlWarehouseClient,
)


def _last_text(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return str(message.content)
    return "No fue posible generar una respuesta."


def collect_artifacts(messages: list[BaseMessage]) -> tuple[AgentArtifact, ...]:
    return tuple(
        message.artifact
        for message in messages
        if isinstance(message, ToolMessage) and message.artifact is not None
    )


class LangChainAgentRunner:
    def __init__(self, agent: Any, sql_client: SqlWarehouseClient) -> None:
        self._agent = agent
        self._sql_client = sql_client

    async def run(self, invocation: AgentInvocation) -> AgentResult:
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
                sql_client=ScopedSqlWarehouseClient(
                    self._sql_client,
                    invocation.principal,
                ),
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
