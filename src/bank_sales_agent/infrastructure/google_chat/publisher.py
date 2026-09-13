from bank_sales_agent.application.dto import ChannelDestination, OutboundMessage
from bank_sales_agent.infrastructure.google_chat.cards import GoogleChatArtifactRenderer
from bank_sales_agent.infrastructure.google_chat.client import GoogleChatClient


class GoogleChatPublisher:
    def __init__(self, client: GoogleChatClient, renderer: GoogleChatArtifactRenderer) -> None:
        self._client = client
        self._renderer = renderer

    async def publish(
        self,
        destination: ChannelDestination,
        message: OutboundMessage,
        idempotency_key: str,
    ) -> None:
        google_message = self._renderer.render(message)
        await self._client.create_message(
            space_name=destination.space_name,
            body=google_message.build(),
            request_id=idempotency_key,
            thread_name=destination.thread_name,
        )
