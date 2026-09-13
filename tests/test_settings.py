import pytest
from pydantic import ValidationError

from bank_sales_agent.infrastructure.config.settings import AppEnvironment, Settings


def test_secrets_are_not_exposed_in_settings_representation() -> None:
    settings = Settings(llm_gateway={"api_key": "super-secret"})

    assert "super-secret" not in repr(settings)
    assert settings.llm_gateway.api_key is not None
    assert settings.llm_gateway.api_key.get_secret_value() == "super-secret"


def test_databricks_credentials_are_required_only_when_enabled() -> None:
    with pytest.raises(ValidationError, match="DATABRICKS__SERVER_HOSTNAME"):
        Settings(databricks={"enabled": True})


def test_non_local_environment_requires_mongodb_uri() -> None:
    with pytest.raises(ValidationError, match="MONGODB__URI"):
        Settings(app_env=AppEnvironment.QA)

    with pytest.raises(ValidationError, match="MONGODB__URI"):
        Settings(app_env=AppEnvironment.PRD, mongodb={"uri": ""})


def test_checkpoint_database_is_isolated_by_environment() -> None:
    settings = Settings(
        app_env=AppEnvironment.DSR,
        mongodb={
            "uri": "mongodb://localhost:27017",
            "database": "sales_agent",
        },
    )

    assert settings.mongodb.database_for(settings.app_env) == "sales_agent_dsr"


def test_nested_environment_variables_are_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_GATEWAY__MODEL_NAME", "openai:test-model")
    monkeypatch.setenv("GOOGLE_CHAT__REQUEST_TIMEOUT_SECONDS", "35")

    settings = Settings(_env_file=None)

    assert settings.llm_gateway.model_name == "openai:test-model"
    assert settings.google_chat.request_timeout_seconds == 35
