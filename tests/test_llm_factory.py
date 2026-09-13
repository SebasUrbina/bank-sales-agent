import pytest
from langchain_openai import ChatOpenAI

from bank_sales_agent.infrastructure.config.settings import LlmGatewaySettings
from bank_sales_agent.infrastructure.llm.factory import build_chat_model


def test_builds_openai_compatible_model_for_apim() -> None:
    settings = LlmGatewaySettings(
        base_url="https://apim.bank.test/llms/",
        model_name="openai:gpt-5-mini",
        api_key="api-secret",
        subscription_key="subscription-secret",
        timeout_seconds=45,
        max_retries=1,
    )

    model = build_chat_model(settings)

    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "gpt-5-mini"
    assert str(model.openai_api_base) == "https://apim.bank.test/llms/gpt-5-mini/v1"
    assert model.max_retries == 1
    assert model.default_headers == {"Ocp-Apim-Subscription-Key": "subscription-secret"}


def test_gateway_api_key_is_required_when_building_client() -> None:
    with pytest.raises(ValueError, match="LLM_GATEWAY__API_KEY"):
        build_chat_model(LlmGatewaySettings())
