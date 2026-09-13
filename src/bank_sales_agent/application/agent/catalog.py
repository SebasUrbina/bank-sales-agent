from dataclasses import dataclass
from enum import StrEnum

from bank_sales_agent.domain.models import Capability, Principal
from bank_sales_agent.domain.policies import can_use


class ToolCategory(StrEnum):
    CUSTOMER = "customer"
    PORTFOLIO = "portfolio"
    INVESTMENTS = "investments"
    OPPORTUNITIES = "opportunities"
    MANAGEMENT = "management"


@dataclass(frozen=True)
class AgentToolSpec:
    name: str
    capability: Capability
    category: ToolCategory


TOOL_CATALOG: tuple[AgentToolSpec, ...] = (
    AgentToolSpec("customer_360", Capability.CUSTOMER_360, ToolCategory.CUSTOMER),
    AgentToolSpec(
        "list_prioritized_customers",
        Capability.LIST_CUSTOMERS,
        ToolCategory.PORTFOLIO,
    ),
)


def visible_tool_names(principal: Principal) -> frozenset[str]:
    """Define visibilidad para el modelo; no reemplaza la autorizacion del caso de uso."""
    return frozenset(spec.name for spec in TOOL_CATALOG if can_use(principal, spec.capability))
