from typing import Protocol

from app.application.dto import AgentInvocation, AgentResult
from app.domain.models import Principal


class EmployeeDirectoryRepository(Protocol):
    async def find_by_email(self, user_email: str) -> Principal | None: ...


class AgentRunner(Protocol):
    async def run(self, invocation: AgentInvocation) -> AgentResult: ...
