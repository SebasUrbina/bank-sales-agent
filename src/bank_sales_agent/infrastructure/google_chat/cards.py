from decimal import Decimal

from bank_sales_agent.application.artifacts import (
    AgentArtifact,
    Customer360Artifact,
    PrioritizedCustomersArtifact,
)
from bank_sales_agent.application.dto import OutboundMessage
from bank_sales_agent.domain.models import Customer360, PrioritizedCustomer
from bank_sales_agent.infrastructure.google_chat.models import (
    GoogleChatCard,
    GoogleChatCardHeader,
    GoogleChatCardV2,
    GoogleChatDecoratedText,
    GoogleChatMessage,
    GoogleChatSection,
)


def _money(value: Decimal) -> str:
    return f"${value:,.0f}".replace(",", ".")


def customer_360_card(customer: Customer360) -> GoogleChatCardV2:
    return GoogleChatCardV2(
        card_id=f"customer-{customer.rut}",
        card=GoogleChatCard(
            header=GoogleChatCardHeader(
                title=customer.full_name,
                subtitle=f"RUT {customer.rut}",
            ),
            sections=(
                GoogleChatSection(
                    widgets=(
                        GoogleChatDecoratedText(top_label="Segmento", text=customer.segment),
                        GoogleChatDecoratedText(
                            top_label="Saldo total", text=_money(customer.total_balance)
                        ),
                        GoogleChatDecoratedText(
                            top_label="Productos", text=", ".join(customer.products)
                        ),
                    )
                ),
            ),
        ),
    )


def prioritized_customers_card(
    customers: tuple[PrioritizedCustomer, ...],
) -> GoogleChatCardV2:
    widgets = tuple(
        GoogleChatDecoratedText(
            top_label=f"Prioridad {customer.priority_score:.0%}",
            text=customer.full_name,
            bottom_label=customer.reason,
        )
        for customer in customers
    )
    return GoogleChatCardV2(
        card_id="prioritized-customers",
        card=GoogleChatCard(
            header=GoogleChatCardHeader(
                title="Clientes priorizados",
                subtitle=f"{len(customers)} resultados",
            ),
            sections=(GoogleChatSection(widgets=widgets),),
        ),
    )


def render_artifact(artifact: AgentArtifact) -> GoogleChatCardV2:
    match artifact:
        case Customer360Artifact(customer=customer):
            return customer_360_card(customer)
        case PrioritizedCustomersArtifact(customers=customers):
            return prioritized_customers_card(customers)


class GoogleChatArtifactRenderer:
    def render(self, message: OutboundMessage) -> GoogleChatMessage:
        return GoogleChatMessage(
            text=message.text,
            cards=tuple(render_artifact(artifact) for artifact in message.artifacts),
        )
