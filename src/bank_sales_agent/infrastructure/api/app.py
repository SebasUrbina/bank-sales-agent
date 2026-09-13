import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from bank_sales_agent.application.dto import (
    AgentInvocation,
    ChannelDestination,
    ProcessAgentRequestCommand,
)
from bank_sales_agent.domain.errors import CustomerNotFoundError, ForbiddenError
from bank_sales_agent.infrastructure.api.container import Container, build_container
from bank_sales_agent.infrastructure.api.schemas import (
    GoogleChatEvent,
    InvokeRequest,
    InvokeResponse,
)

logger = logging.getLogger(__name__)


async def process_safely(command: ProcessAgentRequestCommand, container: Container) -> None:
    try:
        await container.process_agent_request.execute(command)
    except Exception:
        logger.exception(
            "background_agent_request_failed",
            extra={"request_id": command.invocation.request_id},
        )


def create_app(container: Container | None = None) -> FastAPI:
    dependencies = container or build_container()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.container = dependencies
        await dependencies.connect()
        try:
            yield
        finally:
            await dependencies.close()

    app = FastAPI(title="Bank Sales Agent", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(ForbiddenError)
    async def forbidden_handler(_: Request, error: ForbiddenError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(error)})

    @app.exception_handler(CustomerNotFoundError)
    async def not_found_handler(_: Request, error: CustomerNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/agent/invoke", response_model=InvokeResponse)
    async def invoke(body: InvokeRequest, request: Request) -> InvokeResponse:
        principal = await request.app.state.container.resolve_principal.execute(body.user_email)
        request_id = str(uuid4())
        result = await request.app.state.container.agent_runner.run(
            AgentInvocation(
                request_id=request_id,
                principal=principal,
                message=body.message,
                thread_id=body.thread_id,
            )
        )
        return InvokeResponse(
            text=result.text,
            artifacts=[asdict(artifact) for artifact in result.artifacts],
            request_id=request_id,
        )

    @app.post("/google-chat/events")
    async def google_chat_event(
        event: GoogleChatEvent,
        request: Request,
        background_tasks: BackgroundTasks,
    ) -> dict[str, object]:
        """Confirma inmediatamente y procesa el agente despues de responder."""
        text = str(event.message.get("text", "")).strip()
        user_email = str(event.user.get("email", "")).strip().lower()
        space_name = str(event.space.get("name", "")).strip()
        if not text or not user_email or not space_name:
            raise HTTPException(status_code=400, detail="Evento de Google Chat incompleto")

        principal = await request.app.state.container.resolve_principal.execute(user_email)
        thread = event.message.get("thread", {})
        thread_name = str(thread.get("name", "")) if isinstance(thread, dict) else None
        request_id = str(uuid4())
        command = ProcessAgentRequestCommand(
            invocation=AgentInvocation(
                request_id=request_id,
                principal=principal,
                message=text,
                thread_id=space_name,
            ),
            destination=ChannelDestination(
                space_name=space_name,
                thread_name=thread_name or None,
            ),
        )
        background_tasks.add_task(process_safely, command, request.app.state.container)
        return {"text": "Estoy procesando tu solicitud…"}

    return app
