from dataclasses import dataclass

from bank_sales_agent.application.artifacts import AgentArtifact
from bank_sales_agent.domain.models import Principal


@dataclass(frozen=True)
class ListCustomersQuery:
    limit: int = 10
    segment: str | None = None
    min_priority: float | None = None
    executive_email: str | None = None


@dataclass(frozen=True)
class AgentInvocation:
    request_id: str
    principal: Principal
    message: str
    thread_id: str


@dataclass(frozen=True)
class AgentResult:
    text: str
    artifacts: tuple[AgentArtifact, ...]


@dataclass(frozen=True)
class ChannelDestination:
    space_name: str
    thread_name: str | None = None


@dataclass(frozen=True)
class OutboundMessage:
    text: str
    artifacts: tuple[AgentArtifact, ...] = ()


@dataclass(frozen=True)
class ProcessAgentRequestCommand:
    invocation: AgentInvocation
    destination: ChannelDestination
