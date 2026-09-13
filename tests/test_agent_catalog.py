from bank_sales_agent.application.agent.catalog import TOOL_CATALOG, visible_tool_names
from bank_sales_agent.application.agent.instructions import build_agent_instructions
from bank_sales_agent.domain.models import Principal, Role


def test_application_agent_policy_builds_role_instructions_and_visibility() -> None:
    principal = Principal("user@bank.test", Role.COMMERCIAL)
    instructions = build_agent_instructions(principal)
    assert "commercial" in instructions
    assert {spec.name for spec in TOOL_CATALOG} == visible_tool_names(principal)
