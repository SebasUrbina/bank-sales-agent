from collections.abc import Sequence
from typing import Protocol

from bank_sales_agent.application.dto import (
    AgentInvocation,
    AgentResult,
    ChannelDestination,
    ListCustomersQuery,
    OutboundMessage,
)
from bank_sales_agent.domain.models import (
    Customer360,
    DataAccessContext,
    Principal,
    PrioritizedCustomer,
)


class EmployeeDirectoryRepository(Protocol):
    async def find_by_email(self, user_email: str) -> Principal | None: ...


class AgentRunner(Protocol):
    async def run(self, invocation: AgentInvocation) -> AgentResult: ...


class ChannelPublisher(Protocol):
    async def publish(
        self,
        destination: ChannelDestination,
        message: OutboundMessage,
        idempotency_key: str,
    ) -> None: ...


class CustomerInsightsRepository(Protocol):
    async def get_customer_360(self, rut: str, access: DataAccessContext) -> Customer360 | None: ...

    async def list_prioritized(
        self, query: ListCustomersQuery, access: DataAccessContext
    ) -> Sequence[PrioritizedCustomer]: ...
