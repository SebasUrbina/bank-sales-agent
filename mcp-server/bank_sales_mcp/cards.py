"""Subconjunto tipado de cardsV2 de Google Chat que publican las tools.

Referencia: https://developers.google.com/workspace/chat/api/reference/rest/v1/cards
"""

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CardModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid", frozen=True
    )


class CardHeader(CardModel):
    title: str
    subtitle: str | None = None
    image_url: str | None = None
    image_type: Literal["SQUARE", "CIRCLE"] | None = None
    image_alt_text: str | None = None


class DecoratedText(CardModel):
    text: str
    top_label: str | None = None
    bottom_label: str | None = None
    wrap_text: bool | None = None


class DecoratedTextWidget(CardModel):
    decorated_text: DecoratedText


class TextParagraph(CardModel):
    text: str


class TextParagraphWidget(CardModel):
    text_paragraph: TextParagraph


class Divider(CardModel):
    pass


class DividerWidget(CardModel):
    divider: Divider = Field(default_factory=Divider)


class OpenLink(CardModel):
    url: str


class OnClick(CardModel):
    open_link: OpenLink


class Button(CardModel):
    text: str
    on_click: OnClick


class ButtonList(CardModel):
    buttons: list[Button] = Field(min_length=1)


class ButtonListWidget(CardModel):
    button_list: ButtonList


Widget = DecoratedTextWidget | TextParagraphWidget | DividerWidget | ButtonListWidget


class Section(CardModel):
    header: str | None = None
    collapsible: bool | None = None
    uncollapsible_widgets_count: int | None = None
    widgets: list[Widget] = Field(min_length=1)


class Card(CardModel):
    header: CardHeader
    sections: list[Section] = Field(min_length=1)


class CardWithId(CardModel):
    card_id: str
    card: Card


class CardsV2Output(CardModel):
    """structuredContent de las tools: el agente publica estas cards tal como vienen."""

    cards_v2: list[CardWithId] = Field(default_factory=list)

    def to_structured_content(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


CARDS_V2_OUTPUT_SCHEMA: dict[str, Any] = CardsV2Output.model_json_schema(
    by_alias=True, mode="serialization"
)


def decorated(text: str, top: str | None = None, bottom: str | None = None) -> DecoratedTextWidget:
    return DecoratedTextWidget(
        decorated_text=DecoratedText(text=text, top_label=top, bottom_label=bottom)
    )


def paragraph(text: str) -> TextParagraphWidget:
    return TextParagraphWidget(text_paragraph=TextParagraph(text=text))


def link_button(text: str, url: str) -> ButtonListWidget:
    return ButtonListWidget(
        button_list=ButtonList(
            buttons=[Button(text=text, on_click=OnClick(open_link=OpenLink(url=url)))]
        )
    )


def money(value: Decimal) -> str:
    return f"${value:,.0f}".replace(",", ".")
