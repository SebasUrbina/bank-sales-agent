import logging
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.application.dto import (
    AgentInvocation,
    ChatThread,
    InboundAttachment,
)
from app.application.ports import AgentRunner
from app.domain.errors import CustomerNotFoundError, ForbiddenError
from app.infrastructure.api.lifespan import create_lifespan
from app.infrastructure.api.schemas import (
    AcceptedResponse,
    AgentRequest,
)
from app.infrastructure.google_chat.publisher import GoogleChatPublisher
from app.settings import Settings

logger = logging.getLogger(__name__)


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


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    api_settings = resolved_settings.api
    app = FastAPI(
        title=api_settings.title,
        version=api_settings.version,
        docs_url="/docs" if api_settings.docs_enabled else None,
        redoc_url="/redoc" if api_settings.docs_enabled else None,
        openapi_url="/openapi.json" if api_settings.docs_enabled else None,
        lifespan=create_lifespan(resolved_settings),
    )

    @app.exception_handler(ForbiddenError)
    async def forbidden_handler(_: Request, error: ForbiddenError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(error)})

    @app.exception_handler(CustomerNotFoundError)
    async def not_found_handler(_: Request, error: CustomerNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/v1/agent/invoke",
        response_model=AcceptedResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def invoke(
        body: AgentRequest,
        request: Request,
        background_tasks: BackgroundTasks,
    ) -> AcceptedResponse:
        """Confirma inmediatamente y procesa el agente despues de responder."""
        principal = await request.app.state.resolve_principal.execute(body.user_email)
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
        background_tasks.add_task(
            process_safely,
            invocation,
            request.app.state.agent_runner,
            request.app.state.google_chat_publisher,
        )
        return AcceptedResponse(request_id=request_id)

    return app
