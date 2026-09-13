import pytest
from langchain.tools import tool

from bank_sales_agent.application.use_cases.customer_360 import GetCustomer360
from bank_sales_agent.application.use_cases.list_customers import ListPrioritizedCustomers
from bank_sales_agent.domain.models import Principal, Role
from bank_sales_agent.infrastructure.agent.tools.registry import ToolRegistry, build_tool_registry
from bank_sales_agent.infrastructure.mock.repositories import MockCustomerInsightsRepository


@tool
def customer_360(rut: str) -> str:
    """Mock de vista 360."""
    return rut


@tool
def list_prioritized_customers(limit: int = 10) -> str:
    """Mock de clientes priorizados."""
    return str(limit)


def test_registry_returns_tools_visible_for_principal() -> None:
    registry = ToolRegistry([customer_360, list_prioritized_customers])
    principal = Principal("user@bank.test", Role.COMMERCIAL)
    assert {item.name for item in registry.for_principal(principal)} == {
        "customer_360",
        "list_prioritized_customers",
    }


def test_data_tools_expose_render_disabled_by_default() -> None:
    repository = MockCustomerInsightsRepository()
    registry = build_tool_registry(
        GetCustomer360(repository),
        ListPrioritizedCustomers(repository),
    )

    for data_tool in registry.all():
        assert data_tool.args_schema is not None
        assert data_tool.args_schema.model_fields["render"].default is False


def test_registry_fails_fast_when_catalog_and_tools_diverge() -> None:
    with pytest.raises(ValueError, match="missing"):
        ToolRegistry([customer_360])
