"""Unit tests for ToolExecutor deterministic execution boundary."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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
    assert result.validated_arguments == raw_args
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


@pytest.mark.asyncio
async def test_tool_executor_rejected_proposals_never_invoke_handler():
    """Execution Safety Invariant:

    Any proposal rejected by ToolExecutor (unknown tool, missing fields, invalid types,
    unexpected arguments, shop_id injection, domain failure) must NEVER invoke
    the registered handler or cause database access through that proposal.
    """
    registry = ToolRegistry()
    mock_handler = AsyncMock()

    registry.register_tool(
        name="get_sales_summary",
        description="Sales summary test tool",
        input_model=GetSalesSummaryInput,
        output_model=GetSalesSummaryOutput,
        handler=mock_handler,
    )

    executor = ToolExecutor(registry=registry)
    mock_db = MagicMock()
    trusted_shop_id = uuid4()

    # Case 1: Missing required field
    result_missing = await executor.execute(
        tool_name="get_sales_summary",
        raw_args={},
        shop_id=trusted_shop_id,
        db=mock_db,
    )
    assert result_missing.is_failure is True
    assert result_missing.error.error_type == "SchemaValidationError"
    mock_handler.assert_not_called()
    mock_db.execute.assert_not_called()

    # Case 2: Incorrect argument type
    result_type = await executor.execute(
        tool_name="get_sales_summary",
        raw_args={"period": 12345},
        shop_id=trusted_shop_id,
        db=mock_db,
    )
    assert result_type.is_failure is True
    assert result_type.error.error_type == "SchemaValidationError"
    mock_handler.assert_not_called()
    mock_db.execute.assert_not_called()

    # Case 3: Unexpected extra argument (extra='forbid')
    result_extra = await executor.execute(
        tool_name="get_sales_summary",
        raw_args={
            "period": {"period_type": "relative", "relative_period": "day"},
            "unauthorized_field": "hacked_value",
        },
        shop_id=trusted_shop_id,
        db=mock_db,
    )
    assert result_extra.is_failure is True
    assert result_extra.error.error_type == "SchemaValidationError"
    mock_handler.assert_not_called()
    mock_db.execute.assert_not_called()

    # Case 4: shop_id injection attempt
    attacker_shop_id = uuid4()
    result_injection = await executor.execute(
        tool_name="get_sales_summary",
        raw_args={
            "period": {"period_type": "relative", "relative_period": "day"},
            "shop_id": str(attacker_shop_id),
        },
        shop_id=trusted_shop_id,
        db=mock_db,
    )
    assert result_injection.is_failure is True
    assert result_injection.error.error_type == "SchemaValidationError"
    mock_handler.assert_not_called()
    mock_db.execute.assert_not_called()

    # Case 5: Reversed date range (schema/domain validation boundary)
    result_reversed = await executor.execute(
        tool_name="get_sales_summary",
        raw_args={
            "period": {
                "period_type": "date_range",
                "date_range": {
                    "start_date": "2026-10-30",
                    "end_date": "2026-10-01",  # Reversed
                },
            }
        },
        shop_id=trusted_shop_id,
        db=mock_db,
    )
    assert result_reversed.is_failure is True
    mock_handler.assert_not_called()
    mock_db.execute.assert_not_called()

    # Case 6: Unknown tool
    result_unknown = await executor.execute(
        tool_name="non_existent_tool",
        raw_args={"foo": "bar"},
        shop_id=trusted_shop_id,
        db=mock_db,
    )
    assert result_unknown.is_failure is True
    assert result_unknown.error.error_type == "ToolNotFoundError"
    mock_handler.assert_not_called()
    mock_db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_tool_executor_trusted_shop_context_propagation():
    """Verifies that handler receives trusted application shop_id context,

    and that model arguments cannot override shop context.
    """
    registry = ToolRegistry()
    received_shop_ids: list[UUID] = []

    async def capturing_handler(shop_id: UUID, input_data: Any, db: AsyncSession):
        received_shop_ids.append(shop_id)
        return GetSalesSummaryOutput(total_revenue=100, transaction_count=1)

    registry.register_tool(
        name="get_sales_summary",
        description="Sales summary test tool",
        input_model=GetSalesSummaryInput,
        output_model=GetSalesSummaryOutput,
        handler=capturing_handler,
    )

    executor = ToolExecutor(registry=registry)
    mock_db = MagicMock()
    trusted_shop_id = uuid4()

    valid_args = {
        "period": {
            "period_type": "relative",
            "relative_period": "day",
        }
    }

    result = await executor.execute(
        tool_name="get_sales_summary",
        raw_args=valid_args,
        shop_id=trusted_shop_id,
        db=mock_db,
    )

    assert result.is_success is True
    assert len(received_shop_ids) == 1
    assert received_shop_ids[0] == trusted_shop_id
