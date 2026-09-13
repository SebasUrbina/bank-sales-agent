from bank_sales_agent.domain.models import Capability, Principal, Role

ROLE_CAPABILITIES: dict[Role, frozenset[Capability]] = {
    Role.COMMERCIAL: frozenset({Capability.CUSTOMER_360, Capability.LIST_CUSTOMERS}),
    Role.INTEGRAL: frozenset({Capability.CUSTOMER_360, Capability.LIST_CUSTOMERS}),
    Role.INVESTMENTS: frozenset({Capability.CUSTOMER_360, Capability.LIST_CUSTOMERS}),
    Role.LEADER: frozenset({Capability.CUSTOMER_360, Capability.LIST_CUSTOMERS}),
    Role.ADMIN: frozenset(Capability),
}


def can_use(principal: Principal, capability: Capability) -> bool:
    return capability in ROLE_CAPABILITIES[principal.role]
