from typing import Self

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabricksSettings(BaseModel):
    enabled: bool = False
    server_hostname: str | None = None
    http_path: str | None = None
    access_token: SecretStr | None = None

    @model_validator(mode="after")
    def validate_credentials(self) -> Self:
        if self.enabled:
            missing = [
                name
                for name, value in (
                    ("DATABRICKS__SERVER_HOSTNAME", self.server_hostname),
                    ("DATABRICKS__HTTP_PATH", self.http_path),
                    ("DATABRICKS__ACCESS_TOKEN", self.access_token),
                )
                if value is None
                or not (
                    value.get_secret_value().strip()
                    if isinstance(value, SecretStr)
                    else value.strip()
                )
            ]
            if missing:
                raise ValueError("Databricks está habilitado pero faltan: " + ", ".join(missing))
        return self


class Settings(BaseSettings):
    """Configuración independiente: sin LLM, Google Chat ni MongoDB."""

    model_config = SettingsConfigDict(
        env_file=".env", env_nested_delimiter="__", extra="ignore", populate_by_name=True
    )
    signing_secret: SecretStr = Field(validation_alias="MCP__SIGNING_SECRET", min_length=32)
    issuer: str = Field(default="bank-sales-agent", validation_alias="MCP__ISSUER")
    audience: str = Field(default="bank-sales-tools", validation_alias="MCP__AUDIENCE")
    host: str = Field(default="0.0.0.0", validation_alias="MCP__HOST")
    port: int = Field(default=8001, ge=1, le=65535, validation_alias="MCP__PORT")
    databricks: DatabricksSettings = Field(default_factory=DatabricksSettings)
