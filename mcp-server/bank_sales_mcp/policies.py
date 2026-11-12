from enum import StrEnum

from bank_sales_contracts.models import Principal, Role


class Capability(StrEnum):
    CUSTOMER_360 = "customer_360"
    LIST_CUSTOMERS = "list_customers"
    PRODUCT_OFFERS = "product_offers"
    PORTFOLIO_MATURITIES = "portfolio_maturities"


_PORTFOLIO = frozenset(
    {Capability.CUSTOMER_360, Capability.LIST_CUSTOMERS, Capability.PORTFOLIO_MATURITIES}
)

ROLE_CAPABILITIES: dict[Role, frozenset[Capability]] = {
    Role.COMMERCIAL: _PORTFOLIO | {Capability.PRODUCT_OFFERS},
    Role.INTEGRAL: _PORTFOLIO | {Capability.PRODUCT_OFFERS},
    Role.INVESTMENTS_ADVISOR: _PORTFOLIO | {Capability.PRODUCT_OFFERS},
    Role.INVESTMENTS_NON_ADVISOR: _PORTFOLIO,
    Role.SERVICE_CENTER: frozenset({Capability.CUSTOMER_360}),
    Role.MANAGER: _PORTFOLIO | {Capability.PRODUCT_OFFERS},
    Role.ADMIN: frozenset(Capability),
}


def can_use(principal: Principal, capability: Capability) -> bool:
    return capability in ROLE_CAPABILITIES[principal.role]
