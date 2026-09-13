from bank_sales_agent.application.dto import AgentResult
from bank_sales_agent.infrastructure.google_chat.cards import GoogleChatArtifactRenderer
from bank_sales_agent.infrastructure.google_chat.client import GoogleChatClient


class GoogleChatPublisher:
    def __init__(self, client: GoogleChatClient, renderer: GoogleChatArtifactRenderer) -> None:
        self._client = client
        self._renderer = renderer

    async def publish(
        self,
        result: AgentResult,
        space_name: str,
        thread_name: str,
        oauth_token: str,
        request_id: str,
    ) -> None:
        google_message = self._renderer.render(result)
        await self._client.create_message(
            space_name=space_name,
            body=google_message.build(),
            request_id=request_id,
            thread_name=thread_name,
            oauth_token=oauth_token,
        )
