from dataclasses import dataclass

from bank_sales_agent.domain.models import Principal


@dataclass(frozen=True)
class AgentContext:
    principal: Principal
    request_id: str
