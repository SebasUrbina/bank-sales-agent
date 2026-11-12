from enum import StrEnum
from pathlib import Path
from typing import Self
from urllib.parse import quote

from pydantic import AnyHttpUrl, BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    LOCAL = "local"
    DSR = "dsr"
    QA = "qa"
    PRD = "prd"


class ApiSettings(BaseModel):
    title: str = "Bank Sales Agent"
    version: str = "0.1.0"
    docs_enabled: bool = True


class MongoSettings(BaseModel):
    uri: SecretStr | None = None
    database: str = "bank_sales_agent"
    checkpoint_collection: str = "checkpoints"
    writes_collection: str = "checkpoint_writes"

    def database_for(self, environment: AppEnvironment) -> str:
        return f"{self.database}_{environment.value}"


class LlmGatewaySettings(BaseModel):
    base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8080/llms")
    model_name: str = "openai:gpt-5-mini"
    api_key: SecretStr | None = None
    subscription_key: SecretStr | None = None
    timeout_seconds: float = Field(default=60.0, gt=0, le=300)
    max_retries: int = Field(default=2, ge=0, le=5)

    @property
    def endpoint_url(self) -> str:
        model_name = self.model_name.removeprefix("openai:")
        return f"{str(self.base_url).rstrip('/')}/{quote(model_name, safe='')}/v1"


class GoogleChatSettings(BaseModel):
    enabled: bool = False
    request_timeout_seconds: float = Field(default=20.0, gt=0, le=120)


class McpSettings(BaseModel):
    model_config = {"extra": "forbid"}

    url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:8001/mcp")
    signing_secret: SecretStr | None = Field(default=None, min_length=32)
    issuer: str = "bank-sales-agent"
    audience: str = "bank-sales-tools"
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    token_ttl_seconds: int = Field(default=120, ge=30, le=600)


class AgentSkillsSettings(BaseModel):
    directories: list[Path] = Field(default_factory=list)
    max_file_bytes: int = Field(default=262144, ge=1024, le=1048576)


class Settings(BaseSettings):
    """Único punto de lectura del environment, organizado por integración."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: AppEnvironment = AppEnvironment.LOCAL
    api: ApiSettings = Field(default_factory=ApiSettings)
    mongodb: MongoSettings = Field(default_factory=MongoSettings)
    llm_gateway: LlmGatewaySettings = Field(default_factory=LlmGatewaySettings)
    agent_skills: AgentSkillsSettings = Field(default_factory=AgentSkillsSettings)
    mcp: McpSettings = Field(default_factory=McpSettings)
    google_chat: GoogleChatSettings = Field(default_factory=GoogleChatSettings)

    @model_validator(mode="after")
    def validate_enabled_integrations(self) -> Self:
        mongo_uri = self.mongodb.uri.get_secret_value().strip() if self.mongodb.uri else ""
        if self.app_env is not AppEnvironment.LOCAL and not mongo_uri:
            raise ValueError(f"MONGODB__URI es obligatorio en APP_ENV={self.app_env.value}")

        return self
