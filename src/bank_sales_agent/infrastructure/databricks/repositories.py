from decimal import Decimal

from bank_sales_agent.application.dto import ListCustomersQuery
from bank_sales_agent.domain.models import Customer360, DataAccessContext, PrioritizedCustomer
from bank_sales_agent.infrastructure.databricks.client import SqlWarehouseClient
from bank_sales_agent.infrastructure.databricks.query_catalog import (
    CUSTOMER_360_SQL,
    LIST_PRIORITIZED_SQL,
)


def _access_parameters(access: DataAccessContext) -> dict[str, object]:
    return {
        "requester_email": access.requester_email,
        "requester_role": access.role.value,
    }


class DatabricksCustomerInsightsRepository:
    def __init__(self, client: SqlWarehouseClient) -> None:
        self._client = client

    async def get_customer_360(self, rut: str, access: DataAccessContext) -> Customer360 | None:
        rows = await self._client.fetch_all(
            CUSTOMER_360_SQL, {"rut": rut, **_access_parameters(access)}
        )
        if not rows:
            return None
        row = rows[0]
        return Customer360(
            rut=str(row["rut"]),
            executive_email=str(row["executive_email"]),
            full_name=str(row["full_name"]),
            segment=str(row["segment"]),
            total_balance=Decimal(str(row["total_balance"])),
            products=tuple(str(value) for value in row["products"]),
        )

    async def list_prioritized(
        self, query: ListCustomersQuery, access: DataAccessContext
    ) -> list[PrioritizedCustomer]:
        rows = await self._client.fetch_all(
            LIST_PRIORITIZED_SQL,
            {
                **_access_parameters(access),
                "executive_email": query.executive_email,
                "segment": query.segment,
                "min_priority": query.min_priority,
                "limit": query.limit,
            },
        )
        return [
            PrioritizedCustomer(
                rut=str(row["rut"]),
                executive_email=str(row["executive_email"]),
                full_name=str(row["full_name"]),
                priority_score=float(row["priority_score"]),
                reason=str(row["priority_reason"]),
            )
            for row in rows
        ]
