from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.ai.contracts.tools import GetSalesSummaryOutput
from app.ai.errors import ToolNotFoundError
from app.ai.registry import default_registry


def test_default_registry_has_candidate_tools():
    tools = default_registry.list_tools()
    tool_names = [t.name for t in tools]

    expected = [
        "get_sales_summary",
        "get_top_products",
        "get_stock_level",
        "get_low_stock_items",
        "get_sales_trend",
        "get_slow_moving_items",
    ]
    for name in expected:
        assert name in tool_names


def test_get_tool_not_found():
    with pytest.raises(ToolNotFoundError):
        default_registry.get_tool("non_existent_tool")


def test_get_openai_tools_format():
    openai_defs = default_registry.get_openai_tools()
    assert len(openai_defs) >= 6

    first_tool = openai_defs[0]
    assert first_tool["type"] == "function"
    assert "name" in first_tool["function"]
    assert "description" in first_tool["function"]
    assert "parameters" in first_tool["function"]


@pytest.mark.asyncio
async def test_execute_tool_success():
    mock_db = AsyncMock()
    mock_summary = GetSalesSummaryOutput(total_revenue="1500.00", transaction_count=5)

    tool_def = default_registry.get_tool("get_sales_summary")
    original_handler = tool_def.handler

    try:
        mock_handler = AsyncMock(return_value=mock_summary)
        # Temporarily replace handler
        object.__setattr__(tool_def, "handler", mock_handler)

        shop_id = uuid4()
        raw_args = {
            "period": {
                "period_type": "relative",
                "relative_period": "month",
            }
        }

        result = await default_registry.execute_tool(
            "get_sales_summary", shop_id, raw_args, mock_db
        )
        assert result == mock_summary
        mock_handler.assert_called_once()
    finally:
        object.__setattr__(tool_def, "handler", original_handler)
