from decimal import Decimal

import pytest

from bank_sales_agent.application.artifacts import Customer360Artifact
from bank_sales_agent.application.dto import (
    AgentInvocation,
    AgentResult,
    ChannelDestination,
    ProcessAgentRequestCommand,
)
from bank_sales_agent.application.use_cases.process_agent_request import ProcessAgentRequest
from bank_sales_agent.domain.models import Customer360, Principal, Role
from bank_sales_agent.infrastructure.google_chat.cards import GoogleChatArtifactRenderer
from bank_sales_agent.infrastructure.google_chat.client import MockGoogleChatClient
from bank_sales_agent.infrastructure.google_chat.publisher import GoogleChatPublisher


class StubAgentRunner:
    async def run(self, invocation: AgentInvocation) -> AgentResult:
        customer = Customer360(
            "11111111-1",
            invocation.principal.email,
            "Ana Perez",
            "Preferente",
            Decimal("24500000"),
            ("Cuenta corriente",),
        )
        return AgentResult("Vista lista", (Customer360Artifact(customer),))


@pytest.mark.asyncio
async def test_process_renders_and_publishes_one_complete_message() -> None:
    client = MockGoogleChatClient()
    publisher = GoogleChatPublisher(client, GoogleChatArtifactRenderer())
    use_case = ProcessAgentRequest(
        StubAgentRunner(),
        publisher,
    )
    command = ProcessAgentRequestCommand(
        invocation=AgentInvocation(
            request_id="5fb9d7ac-984f-4d67-ab18-e34a06fc3fc4",
            principal=Principal("user@bank.test", Role.COMMERCIAL),
            message="vista 360",
            thread_id="internal-thread",
        ),
        destination=ChannelDestination("spaces/AAAA", "spaces/AAAA/threads/BBBB"),
    )

    await use_case.execute(command)

    assert len(client.sent_messages) == 1
    sent = client.sent_messages[0]
    assert sent["request_id"] == command.invocation.request_id
    assert sent["thread_name"] == "spaces/AAAA/threads/BBBB"
    assert sent["body"]["text"] == "Vista lista"
    assert sent["body"]["cardsV2"][0]["cardId"] == "customer-11111111-1"
