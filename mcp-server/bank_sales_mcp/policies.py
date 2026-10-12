from enum import StrEnum

from bank_sales_contracts.models import Principal, Role


class Capability(StrEnum):
    CUSTOMER_360 = "customer_360"
    LIST_CUSTOMERS = "list_customers"


ROLE_CAPABILITIES: dict[Role, frozenset[Capability]] = {
    Role.COMMERCIAL: frozenset({Capability.CUSTOMER_360, Capability.LIST_CUSTOMERS}),
    Role.INTEGRAL: frozenset({Capability.CUSTOMER_360, Capability.LIST_CUSTOMERS}),
    Role.INVESTMENTS_ADVISOR: frozenset({Capability.CUSTOMER_360, Capability.LIST_CUSTOMERS}),
    Role.INVESTMENTS_NON_ADVISOR: frozenset({Capability.CUSTOMER_360, Capability.LIST_CUSTOMERS}),
    Role.SERVICE_CENTER: frozenset({Capability.CUSTOMER_360}),
    Role.MANAGER: frozenset({Capability.CUSTOMER_360, Capability.LIST_CUSTOMERS}),
    Role.ADMIN: frozenset(Capability),
}


def can_use(principal: Principal, capability: Capability) -> bool:
    return capability in ROLE_CAPABILITIES[principal.role]
