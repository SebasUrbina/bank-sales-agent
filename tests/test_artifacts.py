from decimal import Decimal

from langchain.messages import ToolMessage

from bank_sales_agent.application.artifacts import (
    Customer360Artifact,
    PrioritizedCustomersArtifact,
)
from bank_sales_agent.domain.models import Customer360, PrioritizedCustomer
from bank_sales_agent.infrastructure.agent.runner import collect_artifacts
from bank_sales_agent.infrastructure.google_chat.cards import render_artifact


def customer() -> Customer360:
    return Customer360(
        "11111111-1",
        "ejecutivo@bank.test",
        "Ana Perez",
        "Preferente",
        Decimal("24500000"),
        ("Cuenta corriente",),
    )


def test_collects_native_tool_message_artifacts() -> None:
    artifact = Customer360Artifact(customer())
    messages = [ToolMessage(content="para el modelo", tool_call_id="call-1", artifact=artifact)]
    assert collect_artifacts(messages) == (artifact,)


def test_ignores_tool_messages_without_renderable_artifact() -> None:
    messages = [ToolMessage(content="sólo para el modelo", tool_call_id="call-1")]
    assert collect_artifacts(messages) == ()


def test_google_chat_renderer_maps_customer_360() -> None:
    card = render_artifact(Customer360Artifact(customer())).build()
    assert card["cardId"] == "customer-11111111-1"
    assert card["card"]["header"]["title"] == "Ana Perez"


def test_google_chat_renderer_maps_prioritized_list() -> None:
    item = PrioritizedCustomer(
        "11111111-1", "ejecutivo@bank.test", "Ana Perez", 0.93, "oportunidad"
    )
    card = render_artifact(PrioritizedCustomersArtifact((item,))).build()
    assert card["cardId"] == "prioritized-customers"
