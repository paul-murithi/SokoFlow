"""ToolRegistry Component.

The single source of truth for the AI tool surface.
- AI-facing: Tool identity, description, Pydantic input schemas, JSON schema generation for LLM.
- Backend-facing: Deterministic mapping to executable tool handlers.
"""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts.tools import (
    GetLowStockItemsInput,
    GetLowStockItemsOutput,
    GetSalesSummaryInput,
    GetSalesSummaryOutput,
    GetSalesTrendInput,
    GetSalesTrendOutput,
    GetSlowMovingItemsInput,
    GetSlowMovingItemsOutput,
    GetStockLevelInput,
    GetStockLevelOutput,
    GetTopProductsInput,
    GetTopProductsOutput,
)
from app.ai.errors import ToolNotFoundError
from app.ai.handlers.sales_handlers import (
    handle_get_sales_summary,
    handle_get_sales_trend,
    handle_get_top_products,
)
from app.ai.handlers.stock_handlers import (
    handle_get_low_stock_items,
    handle_get_slow_moving_items,
    handle_get_stock_level,
)
from app.ai.validator import ToolValidator


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Immutable metadata and handler binding for an AI tool."""

    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Callable[[UUID, BaseModel, AsyncSession], Awaitable[BaseModel]]


class ToolRegistry:
    """Registry managing AI tool definitions, LLM JSON schemas, and backend handlers."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        input_model: type[BaseModel],
        output_model: type[BaseModel],
        handler: Callable[[UUID, Any, AsyncSession], Awaitable[Any]],
    ) -> None:
        """Registers a tool with its schema models and backend execution handler."""
        tool_def = ToolDefinition(
            name=name,
            description=description,
            input_model=input_model,
            output_model=output_model,
            handler=handler,
        )
        self._tools[name] = tool_def

    def get_tool(self, name: str) -> ToolDefinition:
        """Retrieves tool definition by name or raises ToolNotFoundError."""
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name]

    def list_tools(self) -> list[ToolDefinition]:
        """Returns all registered tool definitions."""
        return list(self._tools.values())

    def get_openai_tools(self) -> list[dict[str, Any]]:
        """Generates OpenAI Function Calling tool definitions for registered tools."""
        openai_tools = []
        for tool in self._tools.values():
            schema = tool.input_model.model_json_schema()

            # Clean schema for OpenAI compatibility
            schema.pop("title", None)

            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": schema,
                    },
                }
            )
        return openai_tools

    async def execute_tool(
        self,
        name: str,
        shop_id: UUID,
        raw_args: dict[str, Any],
        db: AsyncSession,
    ) -> BaseModel:
        """Validates raw LLM arguments and executes the bound backend handler."""
        tool = self.get_tool(name)

        # Multi-stage validation pipeline
        validated_input = ToolValidator.validate_schema(tool.input_model, raw_args)
        ToolValidator.validate_domain(validated_input)

        # Execute backend handler with trusted shop_id context
        return await tool.handler(shop_id, validated_input, db)


def build_default_registry() -> ToolRegistry:
    """Builds and returns the standard SokoFlow Phase 3 ToolRegistry instance pre-loaded

    with candidate analytics tools.
    """
    registry = ToolRegistry()

    registry.register_tool(
        name="get_sales_summary",
        description=(
            "Calculates total revenue and transaction count for a shop over a requested "
            "reporting period."
        ),
        input_model=GetSalesSummaryInput,
        output_model=GetSalesSummaryOutput,
        handler=handle_get_sales_summary,
    )

    registry.register_tool(
        name="get_top_products",
        description=(
            "Returns product rankings by units sold and/or revenue over a requested "
            "reporting period."
        ),
        input_model=GetTopProductsInput,
        output_model=GetTopProductsOutput,
        handler=handle_get_top_products,
    )

    registry.register_tool(
        name="get_stock_level",
        description=(
            "Retrieves current stock level, low-stock threshold, and price for a specific "
            "product ID."
        ),
        input_model=GetStockLevelInput,
        output_model=GetStockLevelOutput,
        handler=handle_get_stock_level,
    )

    registry.register_tool(
        name="get_low_stock_items",
        description=(
            "Returns all products currently at or below their configured low-stock thresholds."
        ),
        input_model=GetLowStockItemsInput,
        output_model=GetLowStockItemsOutput,
        handler=handle_get_low_stock_items,
    )

    registry.register_tool(
        name="get_sales_trend",
        description="Compares sales performance (revenue and transaction volume) between periods.",
        input_model=GetSalesTrendInput,
        output_model=GetSalesTrendOutput,
        handler=handle_get_sales_trend,
    )

    registry.register_tool(
        name="get_slow_moving_items",
        description=(
            "Identifies products with little or no sales activity over a requested "
            "reporting period."
        ),
        input_model=GetSlowMovingItemsInput,
        output_model=GetSlowMovingItemsOutput,
        handler=handle_get_slow_moving_items,
    )

    return registry


default_registry = build_default_registry()
