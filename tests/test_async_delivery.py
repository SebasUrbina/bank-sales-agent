from decimal import Decimal

import pytest

from bank_sales_agent.application.artifacts import Customer360Artifact
from bank_sales_agent.application.dto import (
    AgentResult,
)
from bank_sales_agent.domain.models import Customer360
from bank_sales_agent.infrastructure.google_chat.cards import GoogleChatArtifactRenderer
from bank_sales_agent.infrastructure.google_chat.client import MockGoogleChatClient
from bank_sales_agent.infrastructure.google_chat.publisher import GoogleChatPublisher


@pytest.mark.asyncio
async def test_publisher_renders_and_sends_one_complete_message() -> None:
    client = MockGoogleChatClient()
    publisher = GoogleChatPublisher(client, GoogleChatArtifactRenderer())
    customer = Customer360(
        "11111111-1",
        "user@bank.test",
        "Ana Perez",
        "Preferente",
        Decimal("24500000"),
        ("Cuenta corriente",),
    )
    result = AgentResult("Vista lista", (Customer360Artifact(customer),))
    request_id = "5fb9d7ac-984f-4d67-ab18-e34a06fc3fc4"

    await publisher.publish(
        result=result,
        space_name="spaces/AAAA",
        thread_name="spaces/AAAA/threads/BBBB",
        oauth_token="secret-token",
        request_id=request_id,
    )

    assert len(client.sent_messages) == 1
    sent = client.sent_messages[0]
    assert sent["request_id"] == request_id
    assert sent["thread_name"] == "spaces/AAAA/threads/BBBB"
    assert sent["body"]["text"] == "Vista lista"
    assert sent["body"]["cardsV2"][0]["cardId"] == "customer-11111111-1"
