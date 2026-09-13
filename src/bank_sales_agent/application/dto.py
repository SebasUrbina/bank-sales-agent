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
    attachments: tuple["InboundAttachment", ...] = ()


@dataclass(frozen=True)
class InboundAttachment:
    resource_name: str
    file_name: str
    mime_type: str
    download_uri: str | None = None


@dataclass(frozen=True)
class AgentResult:
    text: str
    artifacts: tuple[AgentArtifact, ...]
