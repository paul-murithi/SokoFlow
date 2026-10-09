"""Unit tests for ToolExecutor deterministic execution boundary."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.ai.contracts.execution import ToolExecutionResult
from app.ai.contracts.tools import GetSalesSummaryInput, GetSalesSummaryOutput
from app.ai.errors import (
    InfrastructureError,
    ProductNotFoundError,
)
from app.ai.executor import ToolExecutor
from app.ai.registry import ToolRegistry


@pytest.mark.asyncio
async def test_tool_executor_success():
    registry = ToolRegistry()
    mock_handler = AsyncMock(
        return_value=GetSalesSummaryOutput(total_revenue=1500, transaction_count=5)
    )

    registry.register_tool(
        name="get_sales_summary",
        description="Sales summary test tool",
        input_model=GetSalesSummaryInput,
        output_model=GetSalesSummaryOutput,
        handler=mock_handler,
    )

    executor = ToolExecutor(registry=registry)
    shop_id = uuid4()
    mock_db = MagicMock()

    raw_args = {
        "period": {
            "period_type": "relative",
            "relative_period": "day",
        }
    }

    result = await executor.execute(
        tool_name="get_sales_summary",
        raw_args=raw_args,
        shop_id=shop_id,
        db=mock_db,
    )

    assert isinstance(result, ToolExecutionResult)
    assert result.is_success is True
    assert result.is_failure is False
    assert result.status == "success"
    assert result.tool == "get_sales_summary"
    assert result.data.total_revenue == 1500
    assert result.data.transaction_count == 5
    assert result.error is None
    mock_handler.assert_called_once()


@pytest.mark.asyncio
async def test_tool_executor_unknown_tool():
    executor = ToolExecutor(registry=ToolRegistry())
    result = await executor.execute(
        tool_name="unregistered_tool_name",
        raw_args={},
        shop_id=uuid4(),
        db=MagicMock(),
    )

    assert result.is_failure is True
    assert result.status == "failure"
    assert result.tool == "unregistered_tool_name"
    assert result.data is None
    assert result.error is not None
    assert result.error.error_type == "ToolNotFoundError"
    assert "not registered" in result.error.message


@pytest.mark.asyncio
async def test_tool_executor_schema_validation_failure():
    registry = ToolRegistry()
    registry.register_tool(
        name="get_sales_summary",
        description="Sales summary test tool",
        input_model=GetSalesSummaryInput,
        output_model=GetSalesSummaryOutput,
        handler=AsyncMock(),
    )

    executor = ToolExecutor(registry=registry)
    result = await executor.execute(
        tool_name="get_sales_summary",
        raw_args={"period": "invalid_string_instead_of_dict"},
        shop_id=uuid4(),
        db=MagicMock(),
    )

    assert result.is_failure is True
    assert result.error.error_type == "SchemaValidationError"
    assert "Schema validation failed" in result.error.message


@pytest.mark.asyncio
async def test_tool_executor_prohibited_shop_id_injection():
    registry = ToolRegistry()
    registry.register_tool(
        name="get_sales_summary",
        description="Sales summary test tool",
        input_model=GetSalesSummaryInput,
        output_model=GetSalesSummaryOutput,
        handler=AsyncMock(),
    )

    executor = ToolExecutor(registry=registry)
    result = await executor.execute(
        tool_name="get_sales_summary",
        raw_args={
            "period": {"period_type": "relative", "relative_period": "day"},
            "shop_id": str(uuid4()),
        },
        shop_id=uuid4(),
        db=MagicMock(),
    )

    assert result.is_failure is True
    assert result.error.error_type == "SchemaValidationError"
    assert "prohibited" in result.error.message


@pytest.mark.asyncio
async def test_tool_executor_domain_validation_failure():
    registry = ToolRegistry()
    fake_product_id = uuid4()
    mock_handler = AsyncMock(side_effect=ProductNotFoundError(fake_product_id))

    registry.register_tool(
        name="get_sales_summary",
        description="Sales summary test tool",
        input_model=GetSalesSummaryInput,
        output_model=GetSalesSummaryOutput,
        handler=mock_handler,
    )

    executor = ToolExecutor(registry=registry)
    result = await executor.execute(
        tool_name="get_sales_summary",
        raw_args={"period": {"period_type": "relative", "relative_period": "day"}},
        shop_id=uuid4(),
        db=MagicMock(),
    )

    assert result.is_failure is True
    assert result.error.error_type == "ProductNotFoundError"
    assert str(fake_product_id) in result.error.message


@pytest.mark.asyncio
async def test_tool_executor_infrastructure_failure():
    registry = ToolRegistry()
    mock_handler = AsyncMock(side_effect=InfrastructureError("PostgreSQL connection failure"))

    registry.register_tool(
        name="get_sales_summary",
        description="Sales summary test tool",
        input_model=GetSalesSummaryInput,
        output_model=GetSalesSummaryOutput,
        handler=mock_handler,
    )

    executor = ToolExecutor(registry=registry)
    result = await executor.execute(
        tool_name="get_sales_summary",
        raw_args={"period": {"period_type": "relative", "relative_period": "day"}},
        shop_id=uuid4(),
        db=MagicMock(),
    )

    assert result.is_failure is True
    assert result.error.error_type == "InfrastructureError"
    assert "PostgreSQL connection failure" in result.error.message


@pytest.mark.asyncio
async def test_tool_executor_unexpected_exception():
    registry = ToolRegistry()
    mock_handler = AsyncMock(side_effect=RuntimeError("Unexpected math divide by zero"))

    registry.register_tool(
        name="get_sales_summary",
        description="Sales summary test tool",
        input_model=GetSalesSummaryInput,
        output_model=GetSalesSummaryOutput,
        handler=mock_handler,
    )

    executor = ToolExecutor(registry=registry)
    result = await executor.execute(
        tool_name="get_sales_summary",
        raw_args={"period": {"period_type": "relative", "relative_period": "day"}},
        shop_id=uuid4(),
        db=MagicMock(),
    )

    assert result.is_failure is True
    assert result.error.error_type == "RuntimeError"
    assert "Unexpected math divide by zero" in result.error.message
