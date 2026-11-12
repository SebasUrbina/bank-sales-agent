from collections.abc import Mapping
from typing import Any, TypedDict

from pydantic import TypeAdapter


class CardV2(TypedDict):
    cardId: str
    card: dict[str, Any]


_CARDS_V2 = TypeAdapter(list[CardV2])


def extract_cards_v2(structured_content: object) -> list[CardV2]:
    """Lee `cardsV2` desde el structuredContent de cualquier tool MCP.

    El widget interno no se valida aquí: el contrato fino lo define cada servidor en su
    outputSchema y Google Chat rechaza cards inválidas al publicarlas.
    """
    if not isinstance(structured_content, Mapping):
        return []
    raw = structured_content.get("cardsV2")
    if not raw:
        return []
    return _CARDS_V2.validate_python(raw)
