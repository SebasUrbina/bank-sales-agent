import asyncio
from typing import Any, Protocol, cast

import google.auth
import httpx
from google.auth.credentials import Credentials
from google.auth.transport.requests import Request

CHAT_BOT_SCOPE = "https://www.googleapis.com/auth/chat.bot"


class AccessTokenProvider(Protocol):
    async def token(self) -> str: ...


class GoogleAuthTokenProvider:
    """Obtiene tokens con ADC; en GCP usa Workload Identity sin claves locales."""

    def __init__(self) -> None:
        credentials, _ = google.auth.default(scopes=[CHAT_BOT_SCOPE])
        self._credentials: Credentials = credentials
        self._lock = asyncio.Lock()

    async def token(self) -> str:
        async with self._lock:
            if not self._credentials.valid:
                await asyncio.to_thread(self._credentials.refresh, Request())
            if self._credentials.token is None:
                raise RuntimeError("Google credentials did not produce an access token")
            return cast(str, self._credentials.token)


class GoogleChatClient(Protocol):
    async def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def create_message(
        self,
        space_name: str,
        body: dict[str, Any],
        request_id: str,
        thread_name: str | None = None,
    ) -> dict[str, Any]: ...


class GoogleChatApiClient:
    BASE_URL = "https://chat.googleapis.com/v1"

    def __init__(self, tokens: AccessTokenProvider) -> None:
        self._tokens = tokens
        self._http: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(20.0))

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def create_message(
        self,
        space_name: str,
        body: dict[str, Any],
        request_id: str,
        thread_name: str | None = None,
    ) -> dict[str, Any]:
        if self._http is None:
            raise RuntimeError("Google Chat client is not connected")
        payload = dict(body)
        if thread_name:
            payload["thread"] = {"name": thread_name}
        parameters = {"requestId": request_id}
        if thread_name:
            parameters["messageReplyOption"] = "REPLY_MESSAGE_OR_FAIL"
        response = await self._http.post(
            f"{self.BASE_URL}/{space_name}/messages",
            params=parameters,
            headers={"Authorization": f"Bearer {await self._tokens.token()}"},
            json=payload,
        )
        response.raise_for_status()
        return dict(response.json())


class MockGoogleChatClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def create_message(
        self,
        space_name: str,
        body: dict[str, Any],
        request_id: str,
        thread_name: str | None = None,
    ) -> dict[str, Any]:
        record = {
            "space_name": space_name,
            "body": body,
            "request_id": request_id,
            "thread_name": thread_name,
        }
        self.sent_messages.append(record)
        return record
