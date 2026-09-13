import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from typing import Annotated, Any

from langchain.tools import ToolRuntime, tool
from pydantic import Field

from bank_sales_agent.application.artifacts import (
    AgentArtifact,
    PrioritizedCustomersArtifact,
)
from bank_sales_agent.domain.errors import ForbiddenError
from bank_sales_agent.domain.models import Capability, PrioritizedCustomer, Role
from bank_sales_agent.domain.policies import can_use
from bank_sales_agent.infrastructure.agent.context import AgentContext

LIST_PRIORITIZED_SQL = """
SELECT
  s.rut,
  a.executive_email,
  c.full_name,
  s.priority_score,
  s.priority_reason
FROM gold.customer_priority_scores s
JOIN gold.customers c ON c.rut = s.rut
JOIN gold.assignments a ON a.rut = s.rut AND a.is_current = TRUE
WHERE (
  :requester_role = 'admin'
  OR (
    :requester_role IN ('commercial', 'integral', 'investments')
    AND a.executive_email = :requester_email
  )
  OR (
    :requester_role = 'leader'
    AND EXISTS (
      SELECT 1 FROM gold.commercial_hierarchy h
      WHERE h.leader_email = :requester_email
        AND h.executive_email = a.executive_email
        AND h.is_current = TRUE
    )
  )
)
  AND (:executive_email IS NULL OR a.executive_email = :executive_email)
  AND (:segment IS NULL OR c.segment = :segment)
  AND (:min_priority IS NULL OR s.priority_score >= :min_priority)
ORDER BY s.priority_score DESC, s.rut
LIMIT :limit
"""


def map_prioritized_customers(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[PrioritizedCustomer, ...]:
    return tuple(
        PrioritizedCustomer(
            rut=str(row["rut"]),
            executive_email=str(row["executive_email"]),
            full_name=str(row["full_name"]),
            priority_score=float(row["priority_score"]),
            reason=str(row["priority_reason"]),
        )
        for row in rows
    )


@tool(response_format="content_and_artifact")
async def list_prioritized_customers(
    runtime: ToolRuntime[AgentContext],
    limit: Annotated[int, Field(ge=1, le=100)] = 10,
    segment: Annotated[str | None, "Segmento comercial opcional"] = None,
    min_priority: Annotated[float | None, Field(ge=0, le=1)] = None,
    executive_email: Annotated[
        str | None, "Email del ejecutivo; sólo para líderes o admins"
    ] = None,
    render: Annotated[bool, "True para mostrar este resultado como card en Google Chat"] = False,
) -> tuple[str, AgentArtifact | None]:
    """Lista clientes priorizados dentro de la cartera autorizada del usuario."""
    principal = runtime.context.principal
    if not can_use(principal, Capability.LIST_CUSTOMERS):
        raise ForbiddenError("Rol sin acceso al listado de clientes")
    if (
        executive_email
        and principal.role not in {Role.LEADER, Role.ADMIN}
        and executive_email != principal.email
    ):
        raise ForbiddenError("El ejecutivo solicitado está fuera del alcance autorizado")

    rows = await runtime.context.sql_client.fetch_all(
        LIST_PRIORITIZED_SQL,
        {
            "executive_email": executive_email,
            "segment": segment,
            "min_priority": min_priority,
            "limit": limit,
        },
    )
    result = map_prioritized_customers(rows)
    content = json.dumps([asdict(item) for item in result], ensure_ascii=False)
    artifact = PrioritizedCustomersArtifact(result) if render else None
    return content, artifact
