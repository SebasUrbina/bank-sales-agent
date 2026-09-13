import json

import pytest
from langchain.tools import ToolRuntime

from bank_sales_agent.application.artifacts import Customer360Artifact
from bank_sales_agent.domain.errors import ForbiddenError
from bank_sales_agent.domain.models import Principal, Role
from bank_sales_agent.infrastructure.agent.context import AgentContext
from bank_sales_agent.infrastructure.agent.tools.customer_360 import customer_360
from bank_sales_agent.infrastructure.agent.tools.customer_portfolio import (
    list_prioritized_customers,
)
from bank_sales_agent.infrastructure.databricks.client import ScopedSqlWarehouseClient
from bank_sales_agent.infrastructure.mock.repositories import (
    EXECUTIVE_ONE,
    EXECUTIVE_TWO,
    MockSqlWarehouseClient,
)


def runtime_for(principal: Principal) -> ToolRuntime[AgentContext]:
    context = AgentContext(
        principal=principal,
        request_id="request-1",
        sql_client=ScopedSqlWarehouseClient(MockSqlWarehouseClient(), principal),
    )
    return ToolRuntime(
        state={},
        context=context,
        config={},
        stream_writer=lambda _: None,
        tool_call_id="call-1",
        store=None,
    )


@pytest.mark.asyncio
async def test_tool_returns_data_to_model_without_artifact_by_default() -> None:
    assert customer_360.coroutine is not None
    content, artifact = await customer_360.coroutine(
        rut="11111111-1",
        runtime=runtime_for(Principal(EXECUTIVE_ONE, Role.COMMERCIAL)),
    )

    assert json.loads(content)["full_name"] == "Ana Perez"
    assert artifact is None


@pytest.mark.asyncio
async def test_tool_returns_artifact_when_render_is_requested() -> None:
    assert customer_360.coroutine is not None
    _, artifact = await customer_360.coroutine(
        rut="11111111-1",
        render=True,
        runtime=runtime_for(Principal(EXECUTIVE_ONE, Role.COMMERCIAL)),
    )

    assert isinstance(artifact, Customer360Artifact)


@pytest.mark.asyncio
async def test_executive_cannot_request_another_executive_portfolio() -> None:
    assert list_prioritized_customers.coroutine is not None
    with pytest.raises(ForbiddenError):
        await list_prioritized_customers.coroutine(
            executive_email=EXECUTIVE_TWO,
            runtime=runtime_for(Principal(EXECUTIVE_ONE, Role.COMMERCIAL)),
        )
