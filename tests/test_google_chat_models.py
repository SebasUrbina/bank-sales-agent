import pytest

from bank_sales_agent.infrastructure.google_chat.models import (
    GoogleChatCard,
    GoogleChatCardHeader,
    GoogleChatCardV2,
    GoogleChatDecoratedText,
    GoogleChatMessage,
    GoogleChatSection,
)


def test_build_uses_google_chat_camel_case_contract() -> None:
    card = GoogleChatCardV2(
        card_id="customer-1",
        card=GoogleChatCard(
            header=GoogleChatCardHeader(
                title="Cliente",
                image_url="https://example.com/avatar.png",
            ),
            sections=(
                GoogleChatSection(
                    widgets=(GoogleChatDecoratedText(text="Preferente", top_label="Segmento"),)
                ),
            ),
        ),
    )

    payload = GoogleChatMessage("Resultado", (card,)).build()

    assert payload["cardsV2"][0]["cardId"] == "customer-1"
    assert payload["cardsV2"][0]["card"]["header"]["imageUrl"].endswith("avatar.png")
    widget = payload["cardsV2"][0]["card"]["sections"][0]["widgets"][0]
    assert widget == {"decoratedText": {"text": "Preferente", "topLabel": "Segmento"}}


def test_section_rejects_empty_widgets() -> None:
    with pytest.raises(ValueError, match="at least one widget"):
        GoogleChatSection(widgets=())
