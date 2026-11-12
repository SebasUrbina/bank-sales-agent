from dataclasses import dataclass, field

from app.domain.models import Principal


@dataclass(frozen=True)
class ChatThread:
    """Hilo de Google Chat donde se publican cards y la respuesta final."""

    space_name: str
    thread_name: str
    user_oauth_token: str = field(repr=False)


@dataclass(frozen=True)
class AgentInvocation:
    request_id: str
    principal: Principal
    message: str
    chat: ChatThread
    attachments: tuple["InboundAttachment", ...] = ()

    @property
    def thread_id(self) -> str:
        return self.chat.thread_name


@dataclass(frozen=True)
class InboundAttachment:
    resource_name: str
    file_name: str
    mime_type: str
    download_uri: str | None = None


@dataclass(frozen=True)
class AgentResult:
    text: str
