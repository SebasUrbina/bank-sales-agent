from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from bank_sales_agent.domain.models import Principal


class SqlWarehouseClient(Protocol):
    async def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def fetch_all(
        self, statement: str, parameters: Mapping[str, Any]
    ) -> Sequence[Mapping[str, Any]]: ...


class DatabricksSqlWarehouseClient:
    """Fachada del connector. Ejecuta I/O bloqueante en un thread pool."""

    def __init__(self, hostname: str, http_path: str, token: str) -> None:
        self._hostname = hostname
        self._http_path = http_path
        self._token = token
        self._connection: Any | None = None

    async def connect(self) -> None:
        import asyncio

        from databricks import sql

        self._connection = await asyncio.to_thread(
            sql.connect,
            server_hostname=self._hostname,
            http_path=self._http_path,
            access_token=self._token,
        )

    async def close(self) -> None:
        import asyncio

        if self._connection is not None:
            await asyncio.to_thread(self._connection.close)
            self._connection = None

    async def fetch_all(
        self, statement: str, parameters: Mapping[str, Any]
    ) -> Sequence[Mapping[str, Any]]:
        import asyncio

        if self._connection is None:
            raise RuntimeError("Databricks client is not connected")
        connection = self._connection

        def run() -> list[dict[str, Any]]:
            with connection.cursor() as cursor:
                cursor.execute(statement, parameters=dict(parameters))
                columns = [column[0] for column in cursor.description]
                return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

        return await asyncio.to_thread(run)


class ScopedSqlWarehouseClient:
    """Inyecta identidad confiable sin exponerla como argumento controlable por el LLM."""

    def __init__(self, client: SqlWarehouseClient, principal: Principal) -> None:
        self._client = client
        self._principal = principal

    async def fetch_all(
        self, statement: str, parameters: Mapping[str, Any]
    ) -> Sequence[Mapping[str, Any]]:
        return await self._client.fetch_all(
            statement,
            {
                **parameters,
                "requester_email": self._principal.email,
                "requester_role": self._principal.role.value,
            },
        )
