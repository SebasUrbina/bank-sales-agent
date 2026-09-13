from collections.abc import Mapping

import pytest

from bank_sales_agent.domain.models import Principal, Role
from bank_sales_agent.infrastructure.agent.tools.customer_360 import CUSTOMER_360_SQL
from bank_sales_agent.infrastructure.agent.tools.customer_portfolio import (
    LIST_PRIORITIZED_SQL,
)
from bank_sales_agent.infrastructure.databricks.client import ScopedSqlWarehouseClient
from bank_sales_agent.infrastructure.mock.repositories import (
    EXECUTIVE_ONE,
    EXECUTIVE_TWO,
    LEADER,
    MockSqlWarehouseClient,
)


class CapturingSqlClient:
    def __init__(self) -> None:
        self.parameters: dict[str, object] = {}

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def fetch_all(
        self, statement: str, parameters: Mapping[str, object]
    ) -> list[dict[str, object]]:
        self.parameters = dict(parameters)
        return []


@pytest.mark.asyncio
async def test_scope_injects_trusted_email_and_role_after_tool_parameters() -> None:
    raw_client = CapturingSqlClient()
    scoped_client = ScopedSqlWarehouseClient(
        raw_client,
        Principal(LEADER, Role.LEADER),
    )

    await scoped_client.fetch_all(
        CUSTOMER_360_SQL,
        {
            "rut": "11111111-1",
            "requester_email": "spoofed@bank.test",
            "requester_role": "admin",
        },
    )

    assert raw_client.parameters == {
        "rut": "11111111-1",
        "requester_email": LEADER,
        "requester_role": "leader",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("principal", "expected_executives"),
    [
        (Principal(EXECUTIVE_ONE, Role.COMMERCIAL), {EXECUTIVE_ONE}),
        (Principal(LEADER, Role.LEADER), {EXECUTIVE_ONE, EXECUTIVE_TWO}),
        (Principal("admin@bank.test", Role.ADMIN), {EXECUTIVE_ONE, EXECUTIVE_TWO}),
    ],
)
async def test_mock_query_applies_same_portfolio_scope(
    principal: Principal,
    expected_executives: set[str],
) -> None:
    client = ScopedSqlWarehouseClient(MockSqlWarehouseClient(), principal)
    rows = await client.fetch_all(
        LIST_PRIORITIZED_SQL,
        {
            "executive_email": None,
            "segment": None,
            "min_priority": None,
            "limit": 10,
        },
    )

    assert {str(row["executive_email"]) for row in rows} == expected_executives


def test_every_tool_query_requires_trusted_scope_parameters() -> None:
    for statement in (CUSTOMER_360_SQL, LIST_PRIORITIZED_SQL):
        assert ":requester_email" in statement
        assert ":requester_role" in statement
        assert "gold.commercial_hierarchy" in statement
