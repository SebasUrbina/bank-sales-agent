from bank_sales_agent.application.ports import EmployeeDirectoryRepository
from bank_sales_agent.domain.errors import ForbiddenError
from bank_sales_agent.domain.models import Principal


class ResolvePrincipal:
    def __init__(self, directory: EmployeeDirectoryRepository) -> None:
        self._directory = directory

    async def execute(self, user_email: str) -> Principal:
        normalized_email = user_email.strip().lower()
        principal = await self._directory.find_by_email(normalized_email)
        if principal is None:
            raise ForbiddenError("Usuario no habilitado para el agente comercial")
        return principal
