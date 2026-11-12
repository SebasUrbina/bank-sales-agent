"""FastMCP aplica visibilidad y autorización usando identidad del backend."""

import json
from collections.abc import Awaitable, Callable, Sequence
from contextlib import AbstractAsyncContextManager
from contextvars import ContextVar
from typing import Annotated, Any

from bank_sales_contracts.errors import DomainError, ForbiddenError
from bank_sales_contracts.models import Principal
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AuthProvider
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.tool import Tool, ToolResult
from mcp import types as mt
from pydantic import Field

from bank_sales_mcp.cards import CARDS_V2_OUTPUT_SCHEMA
from bank_sales_mcp.catalog import visible_tool_names
from bank_sales_mcp.context import ToolContext
from bank_sales_mcp.results import ToolOutcome
from bank_sales_mcp.sql import (
    ScopedSqlWarehouseClient,
    SqlWarehouseClient,
)
from bank_sales_mcp.tools.customer_360 import customer_360
from bank_sales_mcp.tools.customer_portfolio import (
    list_prioritized_customers,
)
from bank_sales_mcp.tools.maturities import upcoming_maturities
from bank_sales_mcp.tools.product_offers import customer_product_offers

_current_context: ContextVar[ToolContext] = ContextVar("mcp_agent_context")
PrincipalResolver = Callable[[], Awaitable[Principal]]


def _error(error: DomainError) -> ToolError:
    return ToolError(
        json.dumps(
            {"error": {"code": error.code, "message": str(error), "retryable": error.retryable}},
            ensure_ascii=False,
        )
    )


class RoleToolMiddleware(Middleware):
    def __init__(
        self, resolve_principal: PrincipalResolver, sql_client: SqlWarehouseClient
    ) -> None:
        self._resolve_principal = resolve_principal
        self._sql_client = sql_client

    async def on_list_tools(
        self,
        context: MiddlewareContext[mt.ListToolsRequest],
        call_next: CallNext[mt.ListToolsRequest, Sequence[Tool]],
    ) -> Sequence[Tool]:
        principal = await self._resolve_principal()
        visible = visible_tool_names(principal)
        return [tool for tool in await call_next(context) if tool.name in visible]

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        try:
            principal = await self._resolve_principal()
            if context.message.name not in visible_tool_names(principal):
                raise ForbiddenError("Tool fuera del perfil autorizado")
            metadata = context.message.meta.model_dump() if context.message.meta else {}
            token = _current_context.set(
                ToolContext(
                    principal=principal,
                    request_id=str(metadata.get("request_id", "mcp-tool-call")),
                    sql_client=ScopedSqlWarehouseClient(self._sql_client, principal),
                )
            )
            try:
                return await call_next(context)
            finally:
                _current_context.reset(token)
        except DomainError as error:
            raise _error(error) from error


async def _execute(tool: Callable[..., Awaitable[ToolOutcome]], **arguments: Any) -> ToolResult:
    try:
        outcome = await tool(context=_current_context.get(), **arguments)
    except DomainError as error:
        raise _error(error) from error
    return outcome.to_tool_result()


Render = Annotated[
    bool,
    Field(
        description=(
            "true para mostrar el resultado como card en Google Chat. Los datos siempre vuelven "
            "como contexto; usa true sólo si la card aporta valor a la respuesta final."
        )
    ),
]
Rut = Annotated[str, Field(description="RUT chileno del cliente, con dígito verificador")]
READ_ONLY = mt.ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)


def build_mcp_server(
    sql_client: SqlWarehouseClient,
    resolve_principal: PrincipalResolver,
    *,
    auth: AuthProvider | None = None,
    lifespan: Callable[[FastMCP], AbstractAsyncContextManager[dict[str, object]]] | None = None,
) -> FastMCP:
    server = FastMCP("Bank Sales Tools", auth=auth, lifespan=lifespan, mask_error_details=True)
    server.add_middleware(RoleToolMiddleware(resolve_principal, sql_client))

    @server.tool(
        name="customer_360",
        output_schema=CARDS_V2_OUTPUT_SCHEMA,
        annotations=READ_ONLY.model_copy(update={"title": "Vista 360 de cliente"}),
    )
    async def customer_view(rut: Rut, render: Render = False) -> ToolResult:
        """Obtiene la vista consolidada 360 de un cliente autorizado."""
        return await _execute(customer_360, rut=rut, render=render)

    @server.tool(
        name="list_prioritized_customers",
        output_schema=CARDS_V2_OUTPUT_SCHEMA,
        annotations=READ_ONLY.model_copy(update={"title": "Clientes priorizados"}),
    )
    async def portfolio(
        limit: Annotated[int, Field(ge=1, le=100, description="Máximo de clientes")] = 10,
        segment: Annotated[str | None, Field(description="Segmento comercial opcional")] = None,
        min_priority: Annotated[
            float | None, Field(ge=0, le=1, description="Score mínimo entre 0 y 1")
        ] = None,
        executive_email: Annotated[
            str | None, Field(description="Email del ejecutivo; sólo para gerentes o admins")
        ] = None,
        render: Render = False,
    ) -> ToolResult:
        """Lista clientes priorizados dentro de la cartera autorizada del usuario."""
        return await _execute(
            list_prioritized_customers,
            limit=limit,
            segment=segment,
            min_priority=min_priority,
            executive_email=executive_email,
            render=render,
        )

    @server.tool(
        name="customer_product_offers",
        output_schema=CARDS_V2_OUTPUT_SCHEMA,
        annotations=READ_ONLY.model_copy(update={"title": "Ofertas preaprobadas"}),
    )
    async def offers(rut: Rut, render: Render = False) -> ToolResult:
        """Lista ofertas preaprobadas vigentes de un cliente autorizado."""
        return await _execute(customer_product_offers, rut=rut, render=render)

    @server.tool(
        name="upcoming_maturities",
        output_schema=CARDS_V2_OUTPUT_SCHEMA,
        annotations=READ_ONLY.model_copy(update={"title": "Vencimientos próximos"}),
    )
    async def maturities(
        days: Annotated[int, Field(ge=1, le=90, description="Horizonte en días")] = 30,
        limit: Annotated[int, Field(ge=1, le=100, description="Máximo de productos")] = 20,
        render: Render = False,
    ) -> ToolResult:
        """Lista productos de la cartera autorizada que vencen en los próximos días."""
        return await _execute(upcoming_maturities, days=days, limit=limit, render=render)

    return server
