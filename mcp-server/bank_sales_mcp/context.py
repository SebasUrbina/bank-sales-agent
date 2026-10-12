from dataclasses import dataclass

from bank_sales_contracts.models import Principal

from bank_sales_mcp.sql import ScopedSqlWarehouseClient


@dataclass(frozen=True)
class ToolContext:
    principal: Principal
    request_id: str
    sql_client: ScopedSqlWarehouseClient
