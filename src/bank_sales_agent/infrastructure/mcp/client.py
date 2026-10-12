import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import jwt
from fastmcp import Client

from bank_sales_agent.domain.models import Principal
from bank_sales_agent.infrastructure.config.settings import McpSettings


def issue_token(principal: Principal, settings: McpSettings) -> str:
    if settings.signing_secret is None:
        raise ValueError("MCP__SIGNING_SECRET es obligatorio")
    now = int(time.time())
    return jwt.encode(
        {
            "sub": principal.email,
            "iss": settings.issuer,
            "aud": settings.audience,
            "iat": now,
            "exp": now + settings.token_ttl_seconds,
        },
        settings.signing_secret.get_secret_value(),
        algorithm="HS256",
    )


class McpToolGateway:
    def __init__(self, settings: McpSettings) -> None:
        if settings.signing_secret is None:
            raise ValueError("MCP__SIGNING_SECRET es obligatorio para conectar al servidor externo")
        self._settings = settings

    @asynccontextmanager
    async def connect(self, principal: Principal) -> AsyncIterator[Client[Any]]:
        client = Client(
            str(self._settings.url),
            auth=issue_token(principal, self._settings),
            timeout=self._settings.timeout_seconds,
        )
        async with client:
            yield client
