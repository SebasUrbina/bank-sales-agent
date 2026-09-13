import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import (
    ModelRequest,
    ModelResponse,
    ToolCallRequest,
    dynamic_prompt,
    wrap_model_call,
    wrap_tool_call,
)
from langchain.messages import ToolMessage

from bank_sales_agent.application.agent.instructions import build_agent_instructions
from bank_sales_agent.domain.errors import DomainError
from bank_sales_agent.infrastructure.agent.context import AgentContext
from bank_sales_agent.infrastructure.agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


def tool_error_message(
    tool_call_id: str,
    *,
    code: str,
    message: str,
    retryable: bool,
) -> ToolMessage:
    content = json.dumps(
        {"error": {"code": code, "message": message, "retryable": retryable}},
        ensure_ascii=False,
    )
    return ToolMessage(content=content, tool_call_id=tool_call_id, status="error")


@dynamic_prompt
def role_aware_prompt(request: ModelRequest) -> str:
    context = request.runtime.context
    if not isinstance(context, AgentContext):
        raise RuntimeError("AgentContext es obligatorio")
    return build_agent_instructions(context.principal)


@wrap_model_call
async def model_observability(
    request: ModelRequest,
    handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
) -> ModelResponse:
    started = time.monotonic()
    context = request.runtime.context
    if not isinstance(context, AgentContext):
        raise RuntimeError("AgentContext es obligatorio")
    try:
        return await handler(request)
    finally:
        logger.info(
            "agent_model_call",
            extra={
                "request_id": context.request_id,
                "role": context.principal.role.value,
                "duration_ms": round((time.monotonic() - started) * 1000),
            },
        )


@wrap_tool_call
async def safe_tool_errors(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], Awaitable[Any]],
) -> Any:
    tool_call_id = request.tool_call.get("id") or "unknown-tool-call"
    try:
        return await handler(request)
    except DomainError as error:
        return tool_error_message(
            tool_call_id,
            code=error.code,
            message=str(error),
            retryable=error.retryable,
        )
    except Exception:
        logger.exception(
            "unexpected_tool_error",
            extra={"tool_name": request.tool_call["name"]},
        )
        return tool_error_message(
            tool_call_id,
            code="tool_execution_failed",
            message="La fuente de datos no está disponible temporalmente.",
            retryable=False,
        )


def build_tool_selection(registry: ToolRegistry) -> Any:
    @wrap_model_call
    async def select_tools(
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        context = request.runtime.context
        if not isinstance(context, AgentContext):
            raise RuntimeError("AgentContext es obligatorio")
        return await handler(request.override(tools=registry.for_principal(context.principal)))

    return select_tools


def harness_middlewares(registry: ToolRegistry) -> list[Any]:
    """Punto unico para guardrails, auditoria, retries y seleccion de tools."""
    return [
        role_aware_prompt,
        build_tool_selection(registry),
        model_observability,
        safe_tool_errors,
    ]
