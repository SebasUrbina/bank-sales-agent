import logging
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status

from app.application.dto import (
    AgentInvocation,
    ChatThread,
    InboundAttachment,
)
from app.application.ports import AgentRunner
from app.application.use_cases.resolve_principal import ResolvePrincipal
from app.infrastructure.api.schemas import (
    AcceptedResponse,
    AgentRequest,
)
from app.infrastructure.google_chat.publisher import GoogleChatPublisher

logger = logging.getLogger(__name__)

health_router = APIRouter(tags=["health"])
agent_router = APIRouter(prefix="/v1/agent", tags=["agent"])


def get_resolve_principal(request: Request) -> ResolvePrincipal:
    resolver: ResolvePrincipal = request.app.state.resolve_principal
    return resolver


def get_agent_runner(request: Request) -> AgentRunner:
    runner: AgentRunner = request.app.state.agent_runner
    return runner


def get_publisher(request: Request) -> GoogleChatPublisher:
    publisher: GoogleChatPublisher = request.app.state.google_chat_publisher
    return publisher


async def process_safely(
    invocation: AgentInvocation,
    agent_runner: AgentRunner,
    publisher: GoogleChatPublisher,
) -> None:
    try:
        result = await agent_runner.run(invocation)
        await publisher.publish(result, invocation.chat, invocation.request_id)
    except Exception:
        logger.exception(
            "background_agent_request_failed",
            extra={"request_id": invocation.request_id},
        )


@health_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@agent_router.post(
    "/invoke",
    response_model=AcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def invoke(
    body: AgentRequest,
    background_tasks: BackgroundTasks,
    resolve_principal: Annotated[ResolvePrincipal, Depends(get_resolve_principal)],
    agent_runner: Annotated[AgentRunner, Depends(get_agent_runner)],
    publisher: Annotated[GoogleChatPublisher, Depends(get_publisher)],
) -> AcceptedResponse:
    """Confirma inmediatamente y procesa el agente despues de responder."""
    principal = await resolve_principal.execute(body.user_email)
    request_id = str(uuid4())
    invocation = AgentInvocation(
        request_id=request_id,
        principal=principal,
        message=body.message,
        chat=ChatThread(
            space_name=body.space_name,
            thread_name=body.thread_name,
            user_oauth_token=body.user_oauth_token.get_secret_value(),
        ),
        attachments=tuple(
            InboundAttachment(
                resource_name=item.resource_name,
                file_name=item.file_name,
                mime_type=item.mime_type,
                download_uri=str(item.download_uri) if item.download_uri else None,
            )
            for item in body.attachments
        ),
    )
    background_tasks.add_task(process_safely, invocation, agent_runner, publisher)
    return AcceptedResponse(request_id=request_id)
