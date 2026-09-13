from collections.abc import Sequence

from bank_sales_agent.application.dto import ListCustomersQuery
from bank_sales_agent.application.ports import CustomerInsightsRepository
from bank_sales_agent.domain.errors import ForbiddenError, InvalidInputError
from bank_sales_agent.domain.models import (
    Capability,
    DataAccessContext,
    Principal,
    PrioritizedCustomer,
    Role,
)
from bank_sales_agent.domain.policies import can_use


class ListPrioritizedCustomers:
    def __init__(self, repository: CustomerInsightsRepository) -> None:
        self._repository = repository

    async def execute(
        self, principal: Principal, query: ListCustomersQuery
    ) -> Sequence[PrioritizedCustomer]:
        if not can_use(principal, Capability.LIST_CUSTOMERS):
            raise ForbiddenError("Rol sin acceso al listado de clientes")
        if not 1 <= query.limit <= 100:
            raise InvalidInputError("limit debe estar entre 1 y 100")
        if (
            query.executive_email
            and principal.role not in {Role.LEADER, Role.ADMIN}
            and query.executive_email != principal.email
        ):
            raise ForbiddenError("El ejecutivo solicitado esta fuera del alcance autorizado")
        access = DataAccessContext(principal.email, principal.role)
        return await self._repository.list_prioritized(query, access)
