from dataclasses import dataclass

from bank_sales_agent.domain.models import Principal
from bank_sales_agent.infrastructure.databricks.client import ScopedSqlWarehouseClient


@dataclass(frozen=True)
class AgentContext:
    principal: Principal
    request_id: str
    sql_client: ScopedSqlWarehouseClient
