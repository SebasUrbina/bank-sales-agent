import pytest
from pydantic import ValidationError

from bank_sales_mcp.settings import Settings


def test_server_only_requires_its_own_settings() -> None:
    settings = Settings(signing_secret="a" * 32, _env_file=None)
    assert settings.port == 8001
    assert not hasattr(settings, "llm_gateway")
    assert not hasattr(settings, "mongodb")
    assert "a" * 32 not in repr(settings)


def test_databricks_credentials_are_required_only_when_enabled() -> None:
    with pytest.raises(ValidationError, match="DATABRICKS__SERVER_HOSTNAME"):
        Settings(signing_secret="a" * 32, databricks={"enabled": True}, _env_file=None)


def test_server_reads_its_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP__SIGNING_SECRET", "a" * 32)
    monkeypatch.setenv("MCP__PORT", "9001")
    settings = Settings(_env_file=None)
    assert settings.port == 9001
