from typing import Protocol

from bank_sales_agent.application.dto import AgentInvocation, AgentResult
from bank_sales_agent.domain.models import Principal


class EmployeeDirectoryRepository(Protocol):
    async def find_by_email(self, user_email: str) -> Principal | None: ...


class AgentRunner(Protocol):
    async def run(self, invocation: AgentInvocation) -> AgentResult: ...
