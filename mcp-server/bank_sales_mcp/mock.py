from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from typing import Any

from bank_sales_contracts.models import Principal, Role

EXECUTIVE_ONE = "ejecutivo@bank.test"
EXECUTIVE_TWO = "inversiones@bank.test"
LEADER = "lider@bank.test"

EMPLOYEES = {
    EXECUTIVE_ONE: Principal(EXECUTIVE_ONE, Role.COMMERCIAL),
    EXECUTIVE_TWO: Principal(EXECUTIVE_TWO, Role.INVESTMENTS),
    LEADER: Principal(LEADER, Role.LEADER),
    "inversiones-no-asesor@bank.test": Principal(
        "inversiones-no-asesor@bank.test", Role.INVESTMENTS_NON_ADVISOR
    ),
    "integral@bank.test": Principal("integral@bank.test", Role.INTEGRAL),
    "servicio@bank.test": Principal("servicio@bank.test", Role.SERVICE_CENTER),
    "gerente@bank.test": Principal("gerente@bank.test", Role.MANAGER),
    "admin@bank.test": Principal("admin@bank.test", Role.ADMIN),
}

LEADER_RELATIONSHIPS = {
    email: frozenset({EXECUTIVE_ONE, EXECUTIVE_TWO}) for email in (LEADER, "gerente@bank.test")
}

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


_TODAY = date.today()

OFFERS: tuple[dict[str, Any], ...] = (
    {
        "rut": "11111111-1",
        "executive_email": EXECUTIVE_ONE,
        "full_name": "Ana Perez",
        "product_name": "Crédito de consumo",
        "amount": 8_000_000,
        "rate": 0.0129,
        "expires_on": (_TODAY + timedelta(days=20)).isoformat(),
    },
    {
        "rut": "11111111-1",
        "executive_email": EXECUTIVE_ONE,
        "full_name": "Ana Perez",
        "product_name": "Aumento de cupo tarjeta",
        "amount": 2_500_000,
        "rate": 0.0185,
        "expires_on": (_TODAY + timedelta(days=45)).isoformat(),
    },
    {
        "rut": "22222222-2",
        "executive_email": EXECUTIVE_TWO,
        "full_name": "Luis Soto",
        "product_name": "Línea de crédito",
        "amount": 5_000_000,
        "rate": 0.0150,
        "expires_on": (_TODAY + timedelta(days=10)).isoformat(),
    },
)

MATURITIES: tuple[dict[str, Any], ...] = (
    {
        "rut": "11111111-1",
        "executive_email": EXECUTIVE_ONE,
        "full_name": "Ana Perez",
        "product_name": "Depósito a plazo",
        "amount": 15_000_000,
        "days_to_maturity": 5,
    },
    {
        "rut": "22222222-2",
        "executive_email": EXECUTIVE_TWO,
        "full_name": "Luis Soto",
        "product_name": "Depósito a plazo",
        "amount": 40_000_000,
        "days_to_maturity": 12,
    },
    {
        "rut": "33333333-3",
        "executive_email": EXECUTIVE_ONE,
        "full_name": "Marta Diaz",
        "product_name": "Crédito comercial",
        "amount": 9_000_000,
        "days_to_maturity": 60,
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

        if "FROM gold.preapproved_offers o" in statement:
            rut = str(parameters["rut"])
            return [
                row
                for row in OFFERS
                if row["rut"] == rut and _can_access(parameters, str(row["executive_email"]))
            ]

        if "FROM gold.product_maturities m" in statement:
            days = int(parameters["days"])
            rows = [
                {
                    **row,
                    "maturity_date": (_TODAY + timedelta(days=row["days_to_maturity"])).isoformat(),
                }
                for row in MATURITIES
                if row["days_to_maturity"] <= days
                and _can_access(parameters, str(row["executive_email"]))
            ]
            return rows[: int(parameters["limit"])]

        raise ValueError("Query no soportada por MockSqlWarehouseClient")
