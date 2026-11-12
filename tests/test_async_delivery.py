import pytest
from conftest import chat_thread
from pydantic import ValidationError

from app.application.dto import AgentResult
from app.infrastructure.google_chat.cards import extract_cards_v2
from app.infrastructure.google_chat.client import MockGoogleChatClient
from app.infrastructure.google_chat.publisher import GoogleChatPublisher


@pytest.mark.asyncio
async def test_publisher_sends_final_text_with_user_token_in_original_thread(
    chat_client: MockGoogleChatClient,
) -> None:
    request_id = "5fb9d7ac-984f-4d67-ab18-e34a06fc3fc4"

    await GoogleChatPublisher(chat_client).publish(
        AgentResult("Vista lista"), chat_thread(), request_id
    )

    assert chat_client.sent_messages == [
        {
            "space_name": "spaces/AAAA",
            "body": {"text": "Vista lista"},
            "request_id": request_id,
            "thread_name": "spaces/AAAA/threads/BBBB",
            "oauth_token": "user-oauth-token",
        }
    ]


def test_chat_thread_does_not_expose_user_token() -> None:
    assert "user-oauth-token" not in repr(chat_thread())


@pytest.mark.parametrize("content", [None, "text", {}, {"cardsV2": []}, {"other": [1]}])
def test_structured_content_without_cards_is_ignored(content: object) -> None:
    assert extract_cards_v2(content) == []


def test_cards_v2_are_forwarded_without_reinterpreting_widgets() -> None:
    card = {"header": {"title": "Ana"}, "sections": [{"widgets": [{"futureWidget": {}}]}]}
    assert extract_cards_v2({"cardsV2": [{"cardId": "c-1", "card": card}]}) == [
        {"cardId": "c-1", "card": card}
    ]


def test_malformed_cards_v2_envelope_is_rejected() -> None:
    with pytest.raises(ValidationError):
        extract_cards_v2({"cardsV2": [{"card": {}}]})
