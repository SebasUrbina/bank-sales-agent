from collections.abc import Mapping, Sequence
from typing import Any

from bank_sales_agent.domain.models import Principal, Role

EXECUTIVE_ONE = "ejecutivo@bank.test"
EXECUTIVE_TWO = "inversiones@bank.test"
LEADER = "lider@bank.test"

EMPLOYEES = {
    EXECUTIVE_ONE: Principal(EXECUTIVE_ONE, Role.COMMERCIAL),
    EXECUTIVE_TWO: Principal(EXECUTIVE_TWO, Role.INVESTMENTS),
    LEADER: Principal(LEADER, Role.LEADER),
    "admin@bank.test": Principal("admin@bank.test", Role.ADMIN),
}

LEADER_RELATIONSHIPS = {LEADER: frozenset({EXECUTIVE_ONE, EXECUTIVE_TWO})}

CUSTOMERS: tuple[dict[str, Any], ...] = (
    {
        "rut": "11111111-1",
        "executive_email": EXECUTIVE_ONE,
        "full_name": "Ana Perez",
        "segment": "Preferente",
        "total_balance": 24_500_000,
        "products": ["Cuenta corriente", "Deposito"],
    },
    {
        "rut": "22222222-2",
        "executive_email": EXECUTIVE_TWO,
        "full_name": "Luis Soto",
        "segment": "Inversiones",
        "total_balance": 81_000_000,
        "products": ["Cuenta corriente", "Fondos mutuos"],
    },
    {
        "rut": "33333333-3",
        "executive_email": EXECUTIVE_ONE,
        "full_name": "Marta Diaz",
        "segment": "Pyme",
        "total_balance": 12_500_000,
        "products": ["Cuenta corriente", "Credito"],
    },
)

PRIORITIES: tuple[dict[str, Any], ...] = (
    {
        "rut": "11111111-1",
        "executive_email": EXECUTIVE_ONE,
        "full_name": "Ana Perez",
        "priority_score": 0.93,
        "priority_reason": "deposito proximo a vencer",
        "segment": "Preferente",
    },
    {
        "rut": "22222222-2",
        "executive_email": EXECUTIVE_TWO,
        "full_name": "Luis Soto",
        "priority_score": 0.87,
        "priority_reason": "saldo disponible para inversion",
        "segment": "Inversiones",
    },
    {
        "rut": "33333333-3",
        "executive_email": EXECUTIVE_ONE,
        "full_name": "Marta Diaz",
        "priority_score": 0.72,
        "priority_reason": "oportunidad de renovacion",
        "segment": "Pyme",
    },
)


def _can_access(parameters: Mapping[str, Any], executive_email: str) -> bool:
    requester_email = str(parameters["requester_email"])
    role = Role(str(parameters["requester_role"]))
    if role is Role.ADMIN:
        return True
    if role is Role.LEADER:
        return executive_email in LEADER_RELATIONSHIPS.get(requester_email, frozenset())
    return executive_email == requester_email


class MockEmployeeDirectoryRepository:
    async def find_by_email(self, user_email: str) -> Principal | None:
        return EMPLOYEES.get(user_email)


class MockSqlWarehouseClient:
    """Fake local del contrato SQL; aplica el mismo scope que las queries productivas."""

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def fetch_all(
        self, statement: str, parameters: Mapping[str, Any]
    ) -> Sequence[Mapping[str, Any]]:
        if "FROM gold.customers c" in statement:
            rut = str(parameters["rut"])
            return [
                row
                for row in CUSTOMERS
                if row["rut"] == rut and _can_access(parameters, str(row["executive_email"]))
            ]

        if "FROM gold.customer_priority_scores s" in statement:
            rows = [
                row for row in PRIORITIES if _can_access(parameters, str(row["executive_email"]))
            ]
            executive_email = parameters.get("executive_email")
            segment = parameters.get("segment")
            min_priority = parameters.get("min_priority")
            if executive_email:
                rows = [row for row in rows if row["executive_email"] == executive_email]
            if segment:
                rows = [row for row in rows if row["segment"] == segment]
            if min_priority is not None:
                rows = [row for row in rows if float(row["priority_score"]) >= float(min_priority)]
            return rows[: int(parameters["limit"])]

        raise ValueError("Query no soportada por MockSqlWarehouseClient")
