from pydantic import BaseModel, Field, HttpUrl, SecretStr


class AttachmentRequest(BaseModel):
    resource_name: str = Field(min_length=1, max_length=1_000)
    file_name: str = Field(min_length=1, max_length=500)
    mime_type: str = Field(min_length=1, max_length=255)
    download_uri: HttpUrl | None = None


class AgentRequest(BaseModel):
    user_email: str = Field(min_length=3, max_length=320)
    message: str = Field(min_length=1, max_length=8_000)
    space_name: str = Field(pattern=r"^spaces/[^/]+$", max_length=1_000)
    thread_name: str = Field(pattern=r"^spaces/[^/]+/threads/[^/]+$", max_length=1_000)
    user_oauth_token: SecretStr
    attachments: list[AttachmentRequest] = Field(default_factory=list, max_length=10)


class AcceptedResponse(BaseModel):
    request_id: str
    status: str = "accepted"
