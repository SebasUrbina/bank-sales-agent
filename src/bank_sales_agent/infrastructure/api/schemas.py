from typing import Any

from pydantic import BaseModel, Field


class InvokeRequest(BaseModel):
    user_email: str = Field(min_length=3, max_length=320)
    message: str = Field(min_length=1, max_length=8_000)
    thread_id: str = Field(
        min_length=1,
        max_length=1_000,
        description="Identificador canónico que LangChain usa directamente para la conversación",
    )


class InvokeResponse(BaseModel):
    text: str
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    request_id: str


class GoogleChatEvent(BaseModel):
    type: str | None = None
    message: dict[str, Any] = Field(default_factory=dict)
    user: dict[str, Any] = Field(default_factory=dict)
    space: dict[str, Any] = Field(default_factory=dict)
