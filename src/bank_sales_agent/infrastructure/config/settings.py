from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, SecretStr, model_validator
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


class LangChainSettings(BaseModel):
    model_name: str = "openai:gpt-5-mini"
    openai_api_key: SecretStr | None = None


class DatabricksSettings(BaseModel):
    enabled: bool = False
    server_hostname: str | None = None
    http_path: str | None = None
    access_token: SecretStr | None = None


class GoogleChatSettings(BaseModel):
    enabled: bool = False
    request_timeout_seconds: float = Field(default=20.0, gt=0, le=120)


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
    langchain: LangChainSettings = Field(default_factory=LangChainSettings)
    databricks: DatabricksSettings = Field(default_factory=DatabricksSettings)
    google_chat: GoogleChatSettings = Field(default_factory=GoogleChatSettings)

    @model_validator(mode="after")
    def validate_enabled_integrations(self) -> Self:
        mongo_uri = (
            self.mongodb.uri.get_secret_value().strip() if self.mongodb.uri else ""
        )
        if self.app_env is not AppEnvironment.LOCAL and not mongo_uri:
            raise ValueError(
                f"MONGODB__URI es obligatorio en APP_ENV={self.app_env.value}"
            )

        if self.databricks.enabled:
            missing = [
                name
                for name, value in (
                    ("DATABRICKS__SERVER_HOSTNAME", self.databricks.server_hostname),
                    ("DATABRICKS__HTTP_PATH", self.databricks.http_path),
                    ("DATABRICKS__ACCESS_TOKEN", self.databricks.access_token),
                )
                if value is None
                or not (
                    value.get_secret_value().strip()
                    if isinstance(value, SecretStr)
                    else value.strip()
                )
            ]
            if missing:
                raise ValueError(
                    "Databricks está habilitado pero faltan: " + ", ".join(missing)
                )
        return self
