from dataclasses import dataclass, field
from typing import Any

from fastmcp import Client

from bank_sales_agent.domain.models import Principal
from bank_sales_agent.infrastructure.agent.tools.registry import ToolRegistry


@dataclass
class InvocationCapabilities:
    registry: ToolRegistry | None = None
    skill_prompt: str = ""


@dataclass(frozen=True)
class AgentContext:
    principal: Principal
    request_id: str
    mcp_client: Client[Any] | None = None
    capabilities: InvocationCapabilities = field(default_factory=InvocationCapabilities)
