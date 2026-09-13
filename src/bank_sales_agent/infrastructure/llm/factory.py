from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from bank_sales_agent.infrastructure.config.settings import LlmGatewaySettings


def build_chat_model(settings: LlmGatewaySettings) -> BaseChatModel:
    """Construye el cliente OpenAI-compatible expuesto por APIM."""
    if settings.api_key is None:
        raise ValueError("LLM_GATEWAY__API_KEY es obligatorio")

    headers: dict[str, str] = {}
    if settings.subscription_key is not None:
        headers["Ocp-Apim-Subscription-Key"] = settings.subscription_key.get_secret_value()

    return ChatOpenAI(
        model=settings.model_name.removeprefix("openai:"),
        base_url=settings.endpoint_url,
        api_key=settings.api_key,
        default_headers=headers,
        timeout=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )
