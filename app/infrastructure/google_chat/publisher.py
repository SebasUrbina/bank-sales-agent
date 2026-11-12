from app.application.dto import AgentResult, ChatThread
from app.infrastructure.google_chat.client import GoogleChatClient


class GoogleChatPublisher:
    """Publica la respuesta final; las cards ya fueron publicadas por el middleware."""

    def __init__(self, client: GoogleChatClient) -> None:
        self._client = client

    async def publish(self, result: AgentResult, chat: ChatThread, request_id: str) -> None:
        await self._client.create_message(
            space_name=chat.space_name,
            body={"text": result.text},
            request_id=request_id,
            thread_name=chat.thread_name,
            oauth_token=chat.user_oauth_token,
        )
