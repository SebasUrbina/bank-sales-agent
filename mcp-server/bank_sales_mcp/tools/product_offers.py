import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Any

from bank_sales_contracts.errors import ForbiddenError
from bank_sales_contracts.models import ProductOffer

from bank_sales_mcp.cards import (
    Card,
    CardHeader,
    CardWithId,
    Section,
    Widget,
    decorated,
    link_button,
    money,
    paragraph,
)
from bank_sales_mcp.context import ToolContext
from bank_sales_mcp.policies import Capability, can_use
from bank_sales_mcp.results import ToolOutcome

CRM_OFFERS_URL = "https://crm.bank.example/customers/{rut}/offers"

CUSTOMER_OFFERS_SQL = """
SELECT
  o.rut,
  c.full_name,
  o.product_name,
  o.amount,
  o.rate,
  o.expires_on
FROM gold.preapproved_offers o
JOIN gold.customers c ON c.rut = o.rut
JOIN gold.assignments a ON a.rut = o.rut AND a.is_current = TRUE
WHERE o.rut = :rut
  AND o.expires_on >= current_date()
  AND (
    :requester_role = 'admin'
    OR (
      :requester_role IN ('commercial', 'integral', 'investments_advisor')
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
ORDER BY o.amount DESC
"""


def map_product_offers(rows: Sequence[Mapping[str, Any]]) -> tuple[ProductOffer, ...]:
    return tuple(
        ProductOffer(
            rut=str(row["rut"]),
            full_name=str(row["full_name"]),
            product=str(row["product_name"]),
            amount=Decimal(str(row["amount"])),
            rate=float(row["rate"]),
            expires_on=date.fromisoformat(str(row["expires_on"])),
        )
        for row in rows
    )


def product_offers_card(rut: str, offers: tuple[ProductOffer, ...]) -> CardWithId:
    widgets: list[Widget] = [
        decorated(
            money(offer.amount),
            top=offer.product,
            bottom=f"Tasa {offer.rate:.2%} · vence {offer.expires_on:%d-%m-%Y}",
        )
        for offer in offers
    ]
    title = f"Ofertas para {offers[0].full_name}" if offers else "Ofertas preaprobadas"
    return CardWithId(
        card_id=f"offers-{rut}",
        card=Card(
            header=CardHeader(title=title, subtitle=f"RUT {rut}"),
            sections=[
                Section(widgets=widgets or [paragraph("Sin ofertas vigentes para este cliente")]),
                Section(widgets=[link_button("Ver en CRM", CRM_OFFERS_URL.format(rut=rut))]),
            ],
        ),
    )


async def customer_product_offers(
    rut: str,
    context: ToolContext,
    render: bool = False,
) -> ToolOutcome:
    """Lista ofertas preaprobadas vigentes de un cliente autorizado."""
    if not can_use(context.principal, Capability.PRODUCT_OFFERS):
        raise ForbiddenError("Rol sin acceso a ofertas preaprobadas")

    rows = await context.sql_client.fetch_all(CUSTOMER_OFFERS_SQL, {"rut": rut})
    offers = map_product_offers(rows)
    content = json.dumps([asdict(item) for item in offers], ensure_ascii=False, default=str)
    return ToolOutcome(content, (product_offers_card(rut, offers),) if render else ())
