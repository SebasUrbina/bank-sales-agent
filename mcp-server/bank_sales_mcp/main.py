"""Servidor HTTP independiente: python -m bank_sales_mcp.main."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from bank_sales_contracts.errors import ForbiddenError
from bank_sales_contracts.models import Principal
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.dependencies import get_access_token

from bank_sales_mcp.identity import EmployeeDirectoryRepository, ResolvePrincipal
from bank_sales_mcp.mock import (
    MockEmployeeDirectoryRepository,
    MockSqlWarehouseClient,
)
from bank_sales_mcp.server import build_mcp_server
from bank_sales_mcp.settings import Settings
from bank_sales_mcp.sql import (
    DatabricksSqlWarehouseClient,
    SqlWarehouseClient,
)


def create_server(
    settings: Settings,
    *,
    directory: EmployeeDirectoryRepository | None = None,
    sql_client: SqlWarehouseClient | None = None,
) -> FastMCP:
    secret = settings.signing_secret
    if secret is None or len(secret.get_secret_value()) < 32:
        raise ValueError("El servidor HTTP requiere MCP__SIGNING_SECRET de al menos 32 caracteres")
    if sql_client is None:
        if settings.databricks.enabled:
            assert settings.databricks.server_hostname is not None
            assert settings.databricks.http_path is not None
            assert settings.databricks.access_token is not None
            sql_client = DatabricksSqlWarehouseClient(
                settings.databricks.server_hostname,
                settings.databricks.http_path,
                settings.databricks.access_token.get_secret_value(),
            )
        else:
            sql_client = MockSqlWarehouseClient()
    resolver = ResolvePrincipal(directory or MockEmployeeDirectoryRepository())

    async def principal() -> Principal:
        token = get_access_token()
        if token is None or not token.claims or not token.claims.get("exp"):
            raise ForbiddenError("Identidad MCP autenticada y con expiración obligatoria")
        email = token.claims.get("sub")
        if not isinstance(email, str):
            raise ForbiddenError("El token MCP no contiene un usuario válido")
        return await resolver.execute(email)

    @asynccontextmanager
    async def lifespan(_: FastMCP) -> AsyncIterator[dict[str, object]]:
        await sql_client.connect()
        try:
            yield {}
        finally:
            await sql_client.close()

    return build_mcp_server(
        sql_client,
        principal,
        lifespan=lifespan,
        auth=JWTVerifier(
            public_key=secret.get_secret_value(),
            algorithm="HS256",
            issuer=settings.issuer,
            audience=settings.audience,
        ),
    )


def main() -> None:
    settings = Settings()
    create_server(settings).run(transport="http", host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
