import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from decimal import Decimal
from typing import Annotated, Any

from bank_sales_contracts.artifacts import AgentArtifact, Customer360Artifact
from bank_sales_contracts.errors import CustomerNotFoundError, ForbiddenError
from bank_sales_contracts.models import Customer360

from bank_sales_mcp.context import ToolContext
from bank_sales_mcp.policies import Capability, can_use

CUSTOMER_360_SQL = """
SELECT
  c.rut,
  a.executive_email,
  c.full_name,
  c.segment,
  COALESCE(SUM(b.balance), 0) AS total_balance,
  COLLECT_SET(p.product_name) AS products
FROM gold.customers c
JOIN gold.assignments a ON a.rut = c.rut AND a.is_current = TRUE
LEFT JOIN gold.balances b ON b.rut = c.rut
LEFT JOIN gold.products p ON p.rut = c.rut AND p.is_active = TRUE
WHERE c.rut = :rut
  AND (
    :requester_role = 'admin'
    OR (
      :requester_role IN ('commercial', 'integral', 'investments_advisor',
      'investments_non_advisor', 'service_center')
      AND a.executive_email = :requester_email
    )
    OR (
      :requester_role = 'manager'
      AND EXISTS (
        SELECT 1 FROM gold.commercial_hierarchy h
        WHERE h.leader_email = :requester_email
          AND h.executive_email = a.executive_email
          AND h.is_current = TRUE
      )
    )
  )
GROUP BY c.rut, a.executive_email, c.full_name, c.segment
LIMIT 1
"""


def map_customer_360(rows: Sequence[Mapping[str, Any]]) -> Customer360 | None:
    if not rows:
        return None
    row = rows[0]
    return Customer360(
        rut=str(row["rut"]),
        executive_email=str(row["executive_email"]),
        full_name=str(row["full_name"]),
        segment=str(row["segment"]),
        total_balance=Decimal(str(row["total_balance"])),
        products=tuple(str(value) for value in row["products"]),
    )


async def customer_360(
    rut: Annotated[str, "RUT chileno del cliente, con dígito verificador"],
    context: ToolContext,
    render: Annotated[bool, "True para mostrar este resultado como card en Google Chat"] = False,
) -> tuple[str, AgentArtifact | None]:
    """Obtiene la vista consolidada 360 de un cliente autorizado."""
    principal = context.principal
    if not can_use(principal, Capability.CUSTOMER_360):
        raise ForbiddenError("Rol sin acceso a vista 360")

    rows = await context.sql_client.fetch_all(CUSTOMER_360_SQL, {"rut": rut})
    result = map_customer_360(rows)
    if result is None:
        raise CustomerNotFoundError("Cliente no encontrado en el alcance autorizado")

    content = json.dumps(asdict(result), ensure_ascii=False, default=str)
    artifact = Customer360Artifact(result) if render else None
    return content, artifact
