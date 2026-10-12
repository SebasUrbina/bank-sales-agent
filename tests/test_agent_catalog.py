from bank_sales_agent.application.agent.instructions import build_agent_instructions
from bank_sales_agent.domain.models import Principal, Role


def test_instructions_delegate_authorization_to_mcp() -> None:
    instructions = build_agent_instructions(Principal("user@bank.test", Role.COMMERCIAL))
    assert "commercial" in instructions
    assert "El servidor MCP determina tus permisos" in instructions
    assert "no habilita asesoría" not in instructions
