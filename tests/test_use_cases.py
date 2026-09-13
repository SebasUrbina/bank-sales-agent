import pytest

from bank_sales_agent.application.dto import ListCustomersQuery
from bank_sales_agent.application.use_cases.customer_360 import GetCustomer360
from bank_sales_agent.application.use_cases.list_customers import ListPrioritizedCustomers
from bank_sales_agent.domain.errors import CustomerNotFoundError, ForbiddenError
from bank_sales_agent.domain.models import Principal, Role
from bank_sales_agent.infrastructure.mock.repositories import (
    EXECUTIVE_ONE,
    EXECUTIVE_TWO,
    LEADER,
    MockCustomerInsightsRepository,
)


def dependencies() -> tuple[GetCustomer360, ListPrioritizedCustomers]:
    repository = MockCustomerInsightsRepository()
    return GetCustomer360(repository), ListPrioritizedCustomers(repository)


@pytest.mark.asyncio
async def test_customer_outside_portfolio_is_indistinguishable_from_missing() -> None:
    get_360, _ = dependencies()
    with pytest.raises(CustomerNotFoundError):
        await get_360.execute(Principal(EXECUTIVE_ONE, Role.COMMERCIAL), "22222222-2")


@pytest.mark.asyncio
async def test_leader_can_filter_by_related_executive_email() -> None:
    _, list_customers = dependencies()
    rows = await list_customers.execute(
        Principal(LEADER, Role.LEADER),
        ListCustomersQuery(executive_email=EXECUTIVE_TWO),
    )
    assert [row.executive_email for row in rows] == [EXECUTIVE_TWO]


@pytest.mark.asyncio
async def test_executive_cannot_request_another_portfolio() -> None:
    _, list_customers = dependencies()
    with pytest.raises(ForbiddenError):
        await list_customers.execute(
            Principal(EXECUTIVE_ONE, Role.COMMERCIAL),
            ListCustomersQuery(executive_email=EXECUTIVE_TWO),
        )
