from dataclasses import dataclass

from bank_sales_agent.domain.models import Customer360, PrioritizedCustomer


@dataclass(frozen=True)
class Customer360Artifact:
    """Resultado neutral de canal para presentar una vista 360."""

    customer: Customer360


@dataclass(frozen=True)
class PrioritizedCustomersArtifact:
    """Resultado neutral de canal para presentar clientes priorizados."""

    customers: tuple[PrioritizedCustomer, ...]


AgentArtifact = Customer360Artifact | PrioritizedCustomersArtifact
