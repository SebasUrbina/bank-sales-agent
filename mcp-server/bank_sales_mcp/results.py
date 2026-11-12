from dataclasses import dataclass

from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent

from bank_sales_mcp.cards import CardsV2Output, CardWithId


@dataclass(frozen=True)
class ToolOutcome:
    """`context` es lo único que lee el modelo; `cards` sólo se publican en Google Chat."""

    context: str
    cards: tuple[CardWithId, ...] = ()

    def to_tool_result(self) -> ToolResult:
        return ToolResult(
            content=[TextContent(type="text", text=self.context)],
            structured_content=CardsV2Output(cards_v2=list(self.cards)).to_structured_content(),
        )
