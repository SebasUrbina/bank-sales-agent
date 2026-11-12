import json

import pytest
from bank_sales_contracts.errors import ForbiddenError
from bank_sales_contracts.models import Principal, Role
from mcp.types import TextContent

from bank_sales_mcp.cards import ButtonListWidget, CardsV2Output
from bank_sales_mcp.context import ToolContext
from bank_sales_mcp.mock import (
    EXECUTIVE_ONE,
    EXECUTIVE_TWO,
    MockSqlWarehouseClient,
)
from bank_sales_mcp.sql import ScopedSqlWarehouseClient
from bank_sales_mcp.tools.customer_360 import customer_360
from bank_sales_mcp.tools.customer_portfolio import (
    list_prioritized_customers,
)
from bank_sales_mcp.tools.maturities import upcoming_maturities
from bank_sales_mcp.tools.product_offers import customer_product_offers


def context_for(principal: Principal) -> ToolContext:
    return ToolContext(
        principal=principal,
        request_id="request-1",
        sql_client=ScopedSqlWarehouseClient(MockSqlWarehouseClient(), principal),
    )


@pytest.mark.asyncio
async def test_tool_returns_data_to_model_without_cards_by_default() -> None:
    outcome = await customer_360(
        rut="11111111-1",
        context=context_for(Principal(EXECUTIVE_ONE, Role.COMMERCIAL)),
    )

    assert json.loads(outcome.context)["full_name"] == "Ana Perez"
    assert outcome.cards == ()
    assert outcome.to_tool_result().structured_content == {"cardsV2": []}


@pytest.mark.asyncio
async def test_tool_result_separates_model_content_from_cards_v2() -> None:
    outcome = await customer_360(
        rut="11111111-1",
        render=True,
        context=context_for(Principal(EXECUTIVE_ONE, Role.COMMERCIAL)),
    )
    result = outcome.to_tool_result()

    [block] = result.content
    assert isinstance(block, TextContent)
    assert "cardsV2" not in block.text
    assert result.structured_content is not None
    [card] = result.structured_content["cardsV2"]
    assert card["cardId"] == "customer-11111111-1"
    assert card["card"]["header"] == {"title": "Ana Perez", "subtitle": "RUT 11111111-1"}
    assert card["card"]["sections"][0]["widgets"][0] == {
        "decoratedText": {"text": "Preferente", "topLabel": "Segmento"}
    }
    CardsV2Output.model_validate(result.structured_content)


@pytest.mark.asyncio
async def test_executive_cannot_request_another_executive_portfolio() -> None:
    with pytest.raises(ForbiddenError):
        await list_prioritized_customers(
            executive_email=EXECUTIVE_TWO,
            context=context_for(Principal(EXECUTIVE_ONE, Role.COMMERCIAL)),
        )


@pytest.mark.asyncio
async def test_offers_card_includes_crm_button_and_stays_in_scope() -> None:
    context = context_for(Principal(EXECUTIVE_ONE, Role.COMMERCIAL))
    outcome = await customer_product_offers(rut="11111111-1", render=True, context=context)

    assert len(json.loads(outcome.context)) == 2
    widget = outcome.cards[0].card.sections[-1].widgets[0]
    assert isinstance(widget, ButtonListWidget)
    assert widget.button_list.buttons[0].on_click.open_link.url.endswith("/11111111-1/offers")

    other = await customer_product_offers(rut="22222222-2", render=True, context=context)
    assert json.loads(other.context) == []
    payload = other.to_tool_result().structured_content
    assert payload is not None
    widget = payload["cardsV2"][0]["card"]["sections"][0]["widgets"][0]
    assert widget == {"textParagraph": {"text": "Sin ofertas vigentes para este cliente"}}


@pytest.mark.asyncio
async def test_non_advisor_cannot_see_offers() -> None:
    principal = Principal("inversiones-no-asesor@bank.test", Role.INVESTMENTS_NON_ADVISOR)
    with pytest.raises(ForbiddenError):
        await customer_product_offers(rut="22222222-2", context=context_for(principal))


@pytest.mark.asyncio
async def test_maturities_respect_horizon_and_portfolio() -> None:
    context = context_for(Principal(EXECUTIVE_ONE, Role.COMMERCIAL))
    outcome = await upcoming_maturities(days=30, render=True, context=context)

    rows = json.loads(outcome.context)
    assert [row["full_name"] for row in rows] == ["Ana Perez"]
    assert outcome.cards[0].card.header.subtitle == "1 en los próximos 30 días"
