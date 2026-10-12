import pytest
from langchain.tools import tool

from bank_sales_agent.infrastructure.agent.tools.registry import ToolRegistry


@tool
def customer_360(rut: str) -> str:
    """Mock de vista 360."""
    return rut


@tool
def list_prioritized_customers(limit: int = 10) -> str:
    """Mock de clientes priorizados."""
    return str(limit)


def test_registry_accepts_remote_tools_without_local_catalog() -> None:
    registry = ToolRegistry([customer_360])
    assert [item.name for item in registry.all()] == ["customer_360"]


def test_registry_accepts_no_tools_for_a_user() -> None:
    assert ToolRegistry([]).all() == []


def test_registry_rejects_duplicate_names() -> None:
    with pytest.raises(ValueError, match="duplicado"):
        ToolRegistry([customer_360, customer_360])
