import json

import pytest
from bank_sales_contracts.artifacts import Customer360Artifact
from bank_sales_contracts.errors import ForbiddenError
from bank_sales_contracts.models import Principal, Role

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


def context_for(principal: Principal) -> ToolContext:
    return ToolContext(
        principal=principal,
        request_id="request-1",
        sql_client=ScopedSqlWarehouseClient(MockSqlWarehouseClient(), principal),
    )


@pytest.mark.asyncio
async def test_tool_returns_data_to_model_without_artifact_by_default() -> None:
    content, artifact = await customer_360(
        rut="11111111-1",
        context=context_for(Principal(EXECUTIVE_ONE, Role.COMMERCIAL)),
    )

    assert json.loads(content)["full_name"] == "Ana Perez"
    assert artifact is None


@pytest.mark.asyncio
async def test_tool_returns_artifact_when_render_is_requested() -> None:
    _, artifact = await customer_360(
        rut="11111111-1",
        render=True,
        context=context_for(Principal(EXECUTIVE_ONE, Role.COMMERCIAL)),
    )

    assert isinstance(artifact, Customer360Artifact)


@pytest.mark.asyncio
async def test_executive_cannot_request_another_executive_portfolio() -> None:
    with pytest.raises(ForbiddenError):
        await list_prioritized_customers(
            executive_email=EXECUTIVE_TWO,
            context=context_for(Principal(EXECUTIVE_ONE, Role.COMMERCIAL)),
        )
