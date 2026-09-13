from collections.abc import Sequence
from decimal import Decimal

from bank_sales_agent.application.dto import ListCustomersQuery
from bank_sales_agent.domain.models import (
    Customer360,
    DataAccessContext,
    Principal,
    PrioritizedCustomer,
    Role,
)

EXECUTIVE_ONE = "ejecutivo@bank.test"
EXECUTIVE_TWO = "inversiones@bank.test"
LEADER = "lider@bank.test"

CUSTOMERS = (
    Customer360(
        "11111111-1",
        EXECUTIVE_ONE,
        "Ana Perez",
        "Preferente",
        Decimal("24500000"),
        ("Cuenta corriente", "Deposito"),
    ),
    Customer360(
        "22222222-2",
        EXECUTIVE_TWO,
        "Luis Soto",
        "Inversiones",
        Decimal("81000000"),
        ("Cuenta corriente", "Fondos mutuos"),
    ),
    Customer360(
        "33333333-3",
        EXECUTIVE_ONE,
        "Marta Diaz",
        "Pyme",
        Decimal("12500000"),
        ("Cuenta corriente", "Credito"),
    ),
)

PRIORITIES = (
    PrioritizedCustomer(
        "11111111-1", EXECUTIVE_ONE, "Ana Perez", 0.93, "deposito proximo a vencer"
    ),
    PrioritizedCustomer(
        "22222222-2", EXECUTIVE_TWO, "Luis Soto", 0.87, "saldo disponible para inversion"
    ),
    PrioritizedCustomer(
        "33333333-3", EXECUTIVE_ONE, "Marta Diaz", 0.72, "oportunidad de renovacion"
    ),
)

EMPLOYEES = {
    EXECUTIVE_ONE: Principal(EXECUTIVE_ONE, Role.COMMERCIAL),
    EXECUTIVE_TWO: Principal(EXECUTIVE_TWO, Role.INVESTMENTS),
    LEADER: Principal(LEADER, Role.LEADER),
    "admin@bank.test": Principal("admin@bank.test", Role.ADMIN),
}

LEADER_RELATIONSHIPS = {LEADER: frozenset({EXECUTIVE_ONE, EXECUTIVE_TWO})}


def _can_access(access: DataAccessContext, executive_email: str) -> bool:
    if access.role is Role.ADMIN:
        return True
    if access.role is Role.LEADER:
        return executive_email in LEADER_RELATIONSHIPS.get(access.requester_email, frozenset())
    return executive_email == access.requester_email


class MockEmployeeDirectoryRepository:
    async def find_by_email(self, user_email: str) -> Principal | None:
        return EMPLOYEES.get(user_email)


class MockCustomerInsightsRepository:
    async def get_customer_360(self, rut: str, access: DataAccessContext) -> Customer360 | None:
        return next(
            (
                customer
                for customer in CUSTOMERS
                if customer.rut == rut and _can_access(access, customer.executive_email)
            ),
            None,
        )

    async def list_prioritized(
        self, query: ListCustomersQuery, access: DataAccessContext
    ) -> Sequence[PrioritizedCustomer]:
        rows = [item for item in PRIORITIES if _can_access(access, item.executive_email)]
        if query.executive_email:
            rows = [item for item in rows if item.executive_email == query.executive_email]
        if query.min_priority is not None:
            rows = [item for item in rows if item.priority_score >= query.min_priority]
        return rows[: query.limit]
