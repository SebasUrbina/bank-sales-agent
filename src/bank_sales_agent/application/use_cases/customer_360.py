from bank_sales_agent.application.ports import CustomerInsightsRepository
from bank_sales_agent.domain.errors import CustomerNotFoundError, ForbiddenError
from bank_sales_agent.domain.models import Capability, Customer360, DataAccessContext, Principal
from bank_sales_agent.domain.policies import can_use


class GetCustomer360:
    def __init__(
        self,
        repository: CustomerInsightsRepository,
    ) -> None:
        self._repository = repository

    async def execute(self, principal: Principal, rut: str) -> Customer360:
        if not can_use(principal, Capability.CUSTOMER_360):
            raise ForbiddenError("Rol sin acceso a vista 360")
        access = DataAccessContext(principal.email, principal.role)
        customer = await self._repository.get_customer_360(rut, access)
        if customer is None:
            # No revelar si existe fuera del scope del usuario.
            raise CustomerNotFoundError("Cliente no encontrado en el alcance autorizado")
        return customer
