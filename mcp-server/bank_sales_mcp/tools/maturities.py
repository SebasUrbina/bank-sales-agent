import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Any

from bank_sales_contracts.errors import ForbiddenError
from bank_sales_contracts.models import ProductMaturity

from bank_sales_mcp.cards import (
    Card,
    CardHeader,
    CardWithId,
    Section,
    Widget,
    decorated,
    money,
    paragraph,
)
from bank_sales_mcp.context import ToolContext
from bank_sales_mcp.policies import Capability, can_use
from bank_sales_mcp.results import ToolOutcome

UPCOMING_MATURITIES_SQL = """
SELECT
  m.rut,
  a.executive_email,
  c.full_name,
  m.product_name,
  m.amount,
  m.maturity_date
FROM gold.product_maturities m
JOIN gold.customers c ON c.rut = m.rut
JOIN gold.assignments a ON a.rut = m.rut AND a.is_current = TRUE
WHERE m.maturity_date BETWEEN current_date() AND date_add(current_date(), :days)
  AND (
    :requester_role = 'admin'
    OR (
      :requester_role IN ('commercial', 'integral', 'investments_advisor',
        'investments_non_advisor')
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
ORDER BY m.maturity_date, m.rut
LIMIT :limit
"""


def map_maturities(rows: Sequence[Mapping[str, Any]]) -> tuple[ProductMaturity, ...]:
    return tuple(
        ProductMaturity(
            rut=str(row["rut"]),
            executive_email=str(row["executive_email"]),
            full_name=str(row["full_name"]),
            product=str(row["product_name"]),
            amount=Decimal(str(row["amount"])),
            maturity_date=date.fromisoformat(str(row["maturity_date"])),
        )
        for row in rows
    )


def maturities_card(days: int, maturities: tuple[ProductMaturity, ...]) -> CardWithId:
    widgets: list[Widget] = [
        decorated(
            item.full_name,
            top=f"{item.product} · {item.maturity_date:%d-%m-%Y}",
            bottom=money(item.amount),
        )
        for item in maturities
    ]
    return CardWithId(
        card_id="upcoming-maturities",
        card=Card(
            header=CardHeader(
                title="Vencimientos próximos",
                subtitle=f"{len(maturities)} en los próximos {days} días",
            ),
            sections=[Section(widgets=widgets or [paragraph("Sin vencimientos en el período")])],
        ),
    )


async def upcoming_maturities(
    context: ToolContext,
    days: int = 30,
    limit: int = 20,
    render: bool = False,
) -> ToolOutcome:
    """Lista productos de la cartera autorizada que vencen en los próximos días."""
    if not can_use(context.principal, Capability.PORTFOLIO_MATURITIES):
        raise ForbiddenError("Rol sin acceso a vencimientos de cartera")

    rows = await context.sql_client.fetch_all(
        UPCOMING_MATURITIES_SQL, {"days": days, "limit": limit}
    )
    maturities = map_maturities(rows)
    content = json.dumps([asdict(item) for item in maturities], ensure_ascii=False, default=str)
    return ToolOutcome(content, (maturities_card(days, maturities),) if render else ())
