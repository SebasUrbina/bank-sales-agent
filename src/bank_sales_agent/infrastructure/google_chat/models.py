from dataclasses import dataclass
from typing import Any, Protocol


class GoogleChatWidget(Protocol):
    def build(self) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class GoogleChatCardHeader:
    title: str
    subtitle: str | None = None
    image_url: str | None = None
    image_alt_text: str | None = None

    def build(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"title": self.title}
        if self.subtitle is not None:
            payload["subtitle"] = self.subtitle
        if self.image_url is not None:
            payload["imageUrl"] = self.image_url
        if self.image_alt_text is not None:
            payload["imageAltText"] = self.image_alt_text
        return payload


@dataclass(frozen=True, slots=True)
class GoogleChatDecoratedText:
    text: str
    top_label: str | None = None
    bottom_label: str | None = None

    def build(self) -> dict[str, Any]:
        decorated: dict[str, Any] = {"text": self.text}
        if self.top_label is not None:
            decorated["topLabel"] = self.top_label
        if self.bottom_label is not None:
            decorated["bottomLabel"] = self.bottom_label
        return {"decoratedText": decorated}


@dataclass(frozen=True, slots=True)
class GoogleChatTextParagraph:
    text: str

    def build(self) -> dict[str, Any]:
        return {"textParagraph": {"text": self.text}}


@dataclass(frozen=True, slots=True)
class GoogleChatDivider:
    def build(self) -> dict[str, Any]:
        return {"divider": {}}


@dataclass(frozen=True, slots=True)
class GoogleChatOpenLink:
    url: str

    def build(self) -> dict[str, Any]:
        return {"openLink": {"url": self.url}}


@dataclass(frozen=True, slots=True)
class GoogleChatButton:
    text: str
    open_link: GoogleChatOpenLink
    disabled: bool = False

    def build(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "disabled": self.disabled,
            "onClick": self.open_link.build(),
        }


@dataclass(frozen=True, slots=True)
class GoogleChatButtonList:
    buttons: tuple[GoogleChatButton, ...]

    def build(self) -> dict[str, Any]:
        return {"buttonList": {"buttons": [button.build() for button in self.buttons]}}


@dataclass(frozen=True, slots=True)
class GoogleChatSection:
    widgets: tuple[GoogleChatWidget, ...]
    header: str | None = None
    collapsible: bool = False
    uncollapsible_widgets_count: int | None = None

    def __post_init__(self) -> None:
        if not self.widgets:
            raise ValueError("Google Chat section requires at least one widget")

    def build(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"widgets": [widget.build() for widget in self.widgets]}
        if self.header is not None:
            payload["header"] = self.header
        if self.collapsible:
            payload["collapsible"] = True
        if self.uncollapsible_widgets_count is not None:
            payload["uncollapsibleWidgetsCount"] = self.uncollapsible_widgets_count
        return payload


@dataclass(frozen=True, slots=True)
class GoogleChatCard:
    header: GoogleChatCardHeader
    sections: tuple[GoogleChatSection, ...]

    def build(self) -> dict[str, Any]:
        return {
            "header": self.header.build(),
            "sections": [section.build() for section in self.sections],
        }


@dataclass(frozen=True, slots=True)
class GoogleChatCardV2:
    card_id: str
    card: GoogleChatCard

    def build(self) -> dict[str, Any]:
        return {"cardId": self.card_id, "card": self.card.build()}


@dataclass(frozen=True, slots=True)
class GoogleChatMessage:
    text: str
    cards: tuple[GoogleChatCardV2, ...] = ()

    def build(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"text": self.text}
        if self.cards:
            payload["cardsV2"] = [card.build() for card in self.cards]
        return payload
