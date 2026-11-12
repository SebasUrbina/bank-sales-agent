"""Publica en Google Chat las cardsV2 que devuelven las tools, apenas terminan."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from langchain.agents.middleware import AgentMiddleware, AgentState, ToolCallRequest
from langchain.messages import ToolMessage

from app.infrastructure.agent.context import AgentContext
from app.infrastructure.google_chat.cards import extract_cards_v2
from app.infrastructure.google_chat.client import GoogleChatClient

logger = logging.getLogger(__name__)

CARDS_SHOWN = "[Se mostró una card con este resultado en el hilo; no repitas todos sus datos.]"
CARDS_NOT_SHOWN = (
    "[No fue posible mostrar la card al usuario; incluye los datos relevantes en tu respuesta.]"
)


class GoogleChatCardsMiddleware(AgentMiddleware[AgentState, AgentContext]):
    def __init__(self, client: GoogleChatClient) -> None:
        super().__init__()
        self._client = client

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[Any]],
    ) -> Any:
        result = await handler(request)
        if not isinstance(result, ToolMessage) or result.status == "error":
            return result
        context = request.runtime.context
        if not isinstance(context, AgentContext):
            raise RuntimeError("AgentContext es obligatorio")

        try:
            cards = extract_cards_v2(result.artifact)
            if not cards:
                return result
            # Google Chat sólo acepta cards con autenticación de app, no con OAuth de usuario.
            await self._client.create_message(
                space_name=context.chat.space_name,
                body={"cardsV2": cards},
                request_id=str(uuid5(NAMESPACE_URL, f"{context.request_id}/{result.tool_call_id}")),
                thread_name=context.chat.thread_name,
            )
            note = CARDS_SHOWN
        except Exception:
            logger.exception(
                "google_chat_cards_publish_failed",
                extra={"request_id": context.request_id, "tool_name": request.tool_call["name"]},
            )
            note = CARDS_NOT_SHOWN
        return result.model_copy(update={"content": f"{result.content}\n{note}"})
