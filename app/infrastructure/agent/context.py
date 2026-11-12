from dataclasses import dataclass, field
from typing import Any

from fastmcp import Client

from app.application.dto import ChatThread
from app.domain.models import Principal
from app.infrastructure.agent.tools.registry import ToolRegistry


@dataclass
class InvocationCapabilities:
    registry: ToolRegistry | None = None
    skill_prompt: str = ""


@dataclass(frozen=True)
class AgentContext:
    principal: Principal
    request_id: str
    chat: ChatThread
    mcp_client: Client[Any] | None = None
    capabilities: InvocationCapabilities = field(default_factory=InvocationCapabilities)
