from collections.abc import Mapping

import pytest

from bank_sales_agent.application.dto import ListCustomersQuery
from bank_sales_agent.domain.models import DataAccessContext, Role
from bank_sales_agent.infrastructure.databricks.query_catalog import (
    CUSTOMER_360_SQL,
    LIST_PRIORITIZED_SQL,
    PORTFOLIO_ACCESS_PREDICATE,
)
from bank_sales_agent.infrastructure.databricks.repositories import (
    DatabricksCustomerInsightsRepository,
)
from bank_sales_agent.infrastructure.mock.repositories import (
    EXECUTIVE_ONE,
    EXECUTIVE_TWO,
    LEADER,
    MockCustomerInsightsRepository,
)


@pytest.mark.asyncio
async def test_executive_only_sees_customers_assigned_to_own_email() -> None:
    repository = MockCustomerInsightsRepository()
    access = DataAccessContext(EXECUTIVE_ONE, Role.COMMERCIAL)
    rows = await repository.list_prioritized(ListCustomersQuery(), access)
    assert {row.executive_email for row in rows} == {EXECUTIVE_ONE}


@pytest.mark.asyncio
async def test_leader_sees_executives_related_in_databricks_hierarchy() -> None:
    repository = MockCustomerInsightsRepository()
    access = DataAccessContext(LEADER, Role.LEADER)
    rows = await repository.list_prioritized(ListCustomersQuery(), access)
    assert {row.executive_email for row in rows} == {EXECUTIVE_ONE, EXECUTIVE_TWO}


@pytest.mark.asyncio
async def test_admin_sees_every_portfolio() -> None:
    repository = MockCustomerInsightsRepository()
    access = DataAccessContext("admin@bank.test", Role.ADMIN)
    rows = await repository.list_prioritized(ListCustomersQuery(), access)
    assert {row.executive_email for row in rows} == {EXECUTIVE_ONE, EXECUTIVE_TWO}


def test_every_customer_query_contains_central_access_predicate() -> None:
    normalized_predicate = " ".join(PORTFOLIO_ACCESS_PREDICATE.split())
    assert normalized_predicate in " ".join(CUSTOMER_360_SQL.split())
    assert normalized_predicate in " ".join(LIST_PRIORITIZED_SQL.split())


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
async def test_databricks_receives_email_and_role_not_prefetched_executive_list() -> None:
    client = CapturingSqlClient()
    repository = DatabricksCustomerInsightsRepository(client)
    await repository.get_customer_360("11111111-1", DataAccessContext(LEADER, Role.LEADER))
    assert client.parameters == {
        "rut": "11111111-1",
        "requester_email": LEADER,
        "requester_role": "leader",
    }
