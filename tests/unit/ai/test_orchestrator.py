from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.ai.contracts.llm import LLMResponse, NormalizedToolCall
from app.ai.contracts.outcome import OutcomeType
from app.ai.contracts.tools import (
    GetLowStockItemsOutput,
    GetProductPriceOutput,
    GetSalesSummaryOutput,
    GetSalesTrendOutput,
    GetSlowMovingItemsOutput,
    GetTopProductsOutput,
    LowStockItem,
    SlowMovingItem,
)
from app.ai.errors import (
    LLMProviderTimeoutError,
    LLMResponseFormatError,
)
from app.ai.executor import ToolExecutionError, ToolExecutionResult, ToolExecutor
from app.ai.llm_client import LLMClient
from app.ai.orchestrator import AnalyticsOrchestrator
from app.fsm.models import PriorCallContext, ScoredProductMatch


@pytest.fixture
def mock_llm_client():
    client = MagicMock(spec=LLMClient)
    client.generate = AsyncMock()
    return client


@pytest.fixture
def mock_executor():
    executor = MagicMock(spec=ToolExecutor)
    executor.execute = AsyncMock()
    return executor


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.mark.asyncio
async def test_answered_sales_summary(mock_llm_client, mock_executor, mock_db):
    shop_id = uuid4()
    mock_llm_client.generate.return_value = LLMResponse(
        text=None,
        tool_calls=[
            NormalizedToolCall(
                name="get_sales_summary",
                arguments={"period": "today"},
            )
        ],
    )
    sales_data = GetSalesSummaryOutput(
        total_revenue=Decimal("15000.00"),
        transaction_count=12,
    )
    mock_executor.execute.return_value = ToolExecutionResult(
        status="success", tool="get_sales_summary", data=sales_data
    )

    orchestrator = AnalyticsOrchestrator(
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    outcome = await orchestrator.run("How are sales today?", shop_id, mock_db)

    assert outcome.outcome_type == OutcomeType.ANSWERED
    assert outcome.tool == "get_sales_summary"
    assert outcome.data == sales_data
    assert outcome.call == {"name": "get_sales_summary", "arguments": {"period": "today"}}
    mock_executor.execute.assert_awaited_once_with(
        tool_name="get_sales_summary",
        raw_args={"period": "today"},
        shop_id=shop_id,
        db=mock_db,
    )


@pytest.mark.asyncio
async def test_answered_empty_sales_summary(mock_llm_client, mock_executor, mock_db):
    shop_id = uuid4()
    mock_llm_client.generate.return_value = LLMResponse(
        text=None,
        tool_calls=[
            NormalizedToolCall(
                name="get_sales_summary",
                arguments={"period": "today"},
            )
        ],
    )
    sales_data = GetSalesSummaryOutput(
        total_revenue=Decimal("0.00"),
        transaction_count=0,
    )
    mock_executor.execute.return_value = ToolExecutionResult(
        status="success", tool="get_sales_summary", data=sales_data
    )

    orchestrator = AnalyticsOrchestrator(
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    outcome = await orchestrator.run("How are sales today?", shop_id, mock_db)

    assert outcome.outcome_type == OutcomeType.ANSWERED_EMPTY
    assert outcome.tool == "get_sales_summary"
    assert outcome.data == sales_data


@pytest.mark.asyncio
async def test_answered_empty_top_products(mock_llm_client, mock_executor, mock_db):
    shop_id = uuid4()
    mock_llm_client.generate.return_value = LLMResponse(
        text=None,
        tool_calls=[
            NormalizedToolCall(
                name="get_top_products",
                arguments={"period": "today"},
            )
        ],
    )
    empty_top_data = GetTopProductsOutput(
        units=[],
        revenue=[],
    )
    mock_executor.execute.return_value = ToolExecutionResult(
        status="success", tool="get_top_products", data=empty_top_data
    )

    orchestrator = AnalyticsOrchestrator(
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    outcome = await orchestrator.run("What are my top products today?", shop_id, mock_db)

    assert outcome.outcome_type == OutcomeType.ANSWERED_EMPTY
    assert outcome.tool == "get_top_products"


@pytest.mark.asyncio
async def test_needs_selection_on_ambiguous_product(mock_llm_client, mock_executor, mock_db):
    shop_id = uuid4()
    candidate1 = ScoredProductMatch(
        id=uuid4(),
        shop_id=shop_id,
        name="Fresh Milk 500ml",
        sku="FM-500",
        price=Decimal("60.00"),
        similarity_score=0.88,
    )
    candidate2 = ScoredProductMatch(
        id=uuid4(),
        shop_id=shop_id,
        name="Fresh Milk 1L",
        sku="FM-1000",
        price=Decimal("110.00"),
        similarity_score=0.85,
    )

    mock_llm_client.generate.return_value = LLMResponse(
        text=None,
        tool_calls=[
            NormalizedToolCall(
                name="get_stock_level",
                arguments={"product_name": "milk"},
            )
        ],
    )
    mock_executor.execute.return_value = ToolExecutionResult(
        status="failure",
        tool="get_stock_level",
        error=ToolExecutionError(
            error_type="ProductAmbiguousError",
            message="Multiple products match 'milk'",
            details={"candidates": [candidate1.model_dump(), candidate2.model_dump()]},
        ),
    )

    orchestrator = AnalyticsOrchestrator(
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    outcome = await orchestrator.run("Check stock for milk", shop_id, mock_db)

    assert outcome.outcome_type == OutcomeType.NEEDS_SELECTION
    assert outcome.tool == "get_stock_level"
    assert len(outcome.candidates) == 2
    assert outcome.candidates[0].name == "Fresh Milk 500ml"
    assert outcome.pending_call == {
        "tool_name": "get_stock_level",
        "arguments": {"product_name": "milk"},
    }


@pytest.mark.asyncio
async def test_no_analytics_intent_when_no_tool_calls(mock_llm_client, mock_executor, mock_db):
    shop_id = uuid4()
    mock_llm_client.generate.return_value = LLMResponse(
        text="Hello! How can I assist your shop today?",
        tool_calls=[],
    )

    orchestrator = AnalyticsOrchestrator(
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    outcome = await orchestrator.run("Hello there", shop_id, mock_db)

    assert outcome.outcome_type == OutcomeType.NO_ANALYTICS_INTENT
    mock_executor.execute.assert_not_called()


@pytest.mark.asyncio
async def test_bounded_retry_on_multiple_tool_calls(mock_llm_client, mock_executor, mock_db):
    shop_id = uuid4()
    # First attempt: multiple tool calls
    resp1 = LLMResponse(
        text=None,
        tool_calls=[
            NormalizedToolCall(name="get_sales_summary", arguments={"period": "today"}),
            NormalizedToolCall(name="get_stock_level", arguments={"product_name": "sugar"}),
        ],
    )
    # Second attempt: single tool call
    resp2 = LLMResponse(
        text=None,
        tool_calls=[
            NormalizedToolCall(name="get_sales_summary", arguments={"period": "today"}),
        ],
    )
    mock_llm_client.generate.side_effect = [resp1, resp2]

    sales_data = GetSalesSummaryOutput(
        total_revenue=Decimal("1000.00"),
        transaction_count=2,
    )
    mock_executor.execute.return_value = ToolExecutionResult(
        status="success", tool="get_sales_summary", data=sales_data
    )

    orchestrator = AnalyticsOrchestrator(
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    outcome = await orchestrator.run("Sales and stock today", shop_id, mock_db)

    assert outcome.outcome_type == OutcomeType.ANSWERED
    assert outcome.tool == "get_sales_summary"
    assert mock_llm_client.generate.call_count == 2


@pytest.mark.asyncio
async def test_bounded_retry_exhaustion_on_multiple_tool_calls(
    mock_llm_client, mock_executor, mock_db
):
    shop_id = uuid4()
    resp = LLMResponse(
        text=None,
        tool_calls=[
            NormalizedToolCall(name="get_sales_summary", arguments={"period": "today"}),
            NormalizedToolCall(name="get_stock_level", arguments={"product_name": "sugar"}),
        ],
    )
    mock_llm_client.generate.side_effect = [resp, resp]

    orchestrator = AnalyticsOrchestrator(
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    outcome = await orchestrator.run("Sales and stock today", shop_id, mock_db)

    assert outcome.outcome_type == OutcomeType.INVALID_PROPOSAL
    assert "Multiple tool calls" in (outcome.message or "")
    assert mock_llm_client.generate.call_count == 2
    mock_executor.execute.assert_not_called()


@pytest.mark.asyncio
async def test_bounded_retry_on_unknown_tool(mock_llm_client, mock_executor, mock_db):
    shop_id = uuid4()
    resp1 = LLMResponse(
        text=None,
        tool_calls=[NormalizedToolCall(name="unknown_tool", arguments={})],
    )
    resp2 = LLMResponse(
        text=None,
        tool_calls=[NormalizedToolCall(name="get_sales_summary", arguments={"period": "today"})],
    )
    mock_llm_client.generate.side_effect = [resp1, resp2]

    sales_data = GetSalesSummaryOutput(
        total_revenue=Decimal("2000.00"),
        transaction_count=4,
    )
    mock_executor.execute.return_value = ToolExecutionResult(
        status="success", tool="get_sales_summary", data=sales_data
    )

    orchestrator = AnalyticsOrchestrator(
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    outcome = await orchestrator.run("What happened today?", shop_id, mock_db)

    assert outcome.outcome_type == OutcomeType.ANSWERED
    assert outcome.tool == "get_sales_summary"
    assert mock_llm_client.generate.call_count == 2


@pytest.mark.asyncio
async def test_bounded_retry_on_schema_validation_error(mock_llm_client, mock_executor, mock_db):
    shop_id = uuid4()
    resp1 = LLMResponse(
        text=None,
        tool_calls=[
            NormalizedToolCall(
                name="get_sales_summary",
                arguments={"period": "invalid_val"},
            )
        ],
    )
    resp2 = LLMResponse(
        text=None,
        tool_calls=[NormalizedToolCall(name="get_sales_summary", arguments={"period": "today"})],
    )
    mock_llm_client.generate.side_effect = [resp1, resp2]

    mock_executor.execute.side_effect = [
        ToolExecutionResult(
            status="failure",
            tool="get_sales_summary",
            error=ToolExecutionError(
                error_type="SchemaValidationError",
                message="Value error, invalid period",
            ),
        ),
        ToolExecutionResult(
            status="success",
            tool="get_sales_summary",
            data=GetSalesSummaryOutput(
                total_revenue=Decimal("1000.00"),
                transaction_count=1,
            ),
        ),
    ]

    orchestrator = AnalyticsOrchestrator(
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    outcome = await orchestrator.run("Sales today", shop_id, mock_db)

    assert outcome.outcome_type == OutcomeType.ANSWERED
    assert mock_llm_client.generate.call_count == 2
    assert mock_executor.execute.call_count == 2


@pytest.mark.asyncio
async def test_domain_failure_outcome(mock_llm_client, mock_executor, mock_db):
    shop_id = uuid4()
    mock_llm_client.generate.return_value = LLMResponse(
        text=None,
        tool_calls=[
            NormalizedToolCall(name="get_stock_level", arguments={"product_name": "Ghost"})
        ],
    )
    mock_executor.execute.return_value = ToolExecutionResult(
        status="failure",
        tool="get_stock_level",
        error=ToolExecutionError(
            error_type="ProductNotFoundError",
            message="No product matches 'Ghost'",
            details={"search_term": "Ghost"},
        ),
    )

    orchestrator = AnalyticsOrchestrator(
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    outcome = await orchestrator.run("Check stock for Ghost", shop_id, mock_db)

    assert outcome.outcome_type == OutcomeType.DOMAIN_FAILURE
    assert outcome.tool == "get_stock_level"
    assert outcome.error_type == "ProductNotFoundError"
    assert "Ghost" in (outcome.message or "")


@pytest.mark.asyncio
async def test_provider_timeout_error(mock_llm_client, mock_executor, mock_db):
    shop_id = uuid4()
    mock_llm_client.generate.side_effect = LLMProviderTimeoutError(
        "Groq request timed out after 3.0s"
    )

    orchestrator = AnalyticsOrchestrator(
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    outcome = await orchestrator.run("How are sales today?", shop_id, mock_db)

    assert outcome.outcome_type == OutcomeType.PROVIDER_UNAVAILABLE
    assert "timed out" in (outcome.message or "")
    mock_executor.execute.assert_not_called()


@pytest.mark.asyncio
async def test_multi_turn_follow_up_passes_prior_context(mock_llm_client, mock_executor, mock_db):
    shop_id = uuid4()
    prior = PriorCallContext(
        tool_name="get_sales_summary",
        arguments={"period": "today"},
    )
    mock_llm_client.generate.return_value = LLMResponse(
        text=None,
        tool_calls=[
            NormalizedToolCall(
                name="get_sales_summary",
                arguments={"period": "yesterday"},
            )
        ],
    )
    sales_data = GetSalesSummaryOutput(
        total_revenue=Decimal("12000.00"),
        transaction_count=10,
    )
    mock_executor.execute.return_value = ToolExecutionResult(
        status="success", tool="get_sales_summary", data=sales_data
    )

    orchestrator = AnalyticsOrchestrator(
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    outcome = await orchestrator.run("and yesterday?", shop_id, mock_db, prior_context=prior)

    assert outcome.outcome_type == OutcomeType.ANSWERED
    # Verify that prior context was sent to generate
    calls = mock_llm_client.generate.call_args
    messages_passed = calls.kwargs["messages"]
    assert len(messages_passed) == 2
    assert messages_passed[0].role == "assistant"
    assert "Previous tool executed: get_sales_summary" in messages_passed[0].content
    assert messages_passed[1].role == "user"
    assert messages_passed[1].content == "and yesterday?"


@pytest.mark.asyncio
async def test_answered_low_stock_items(mock_llm_client, mock_executor, mock_db):
    shop_id = uuid4()
    mock_llm_client.generate.return_value = LLMResponse(
        text=None,
        tool_calls=[NormalizedToolCall(name="get_low_stock_items", arguments={})],
    )
    items_data = GetLowStockItemsOutput(
        items=[
            LowStockItem(
                product_id=uuid4(),
                product_name="Sugar 1kg",
                current_stock=2,
                low_stock_threshold=5,
            )
        ],
        count=1,
    )
    mock_executor.execute.return_value = ToolExecutionResult(
        status="success", tool="get_low_stock_items", data=items_data
    )

    orchestrator = AnalyticsOrchestrator(
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    outcome = await orchestrator.run("What items are low on stock?", shop_id, mock_db)

    assert outcome.outcome_type == OutcomeType.ANSWERED
    assert outcome.tool == "get_low_stock_items"
    assert outcome.data == items_data


@pytest.mark.asyncio
async def test_answered_sales_trend(mock_llm_client, mock_executor, mock_db):
    shop_id = uuid4()
    mock_llm_client.generate.return_value = LLMResponse(
        text=None,
        tool_calls=[NormalizedToolCall(name="get_sales_trend", arguments={"period": "this week"})],
    )
    trend_data = GetSalesTrendOutput(
        current_period_revenue=Decimal("15000.00"),
        previous_period_revenue=Decimal("10000.00"),
        revenue_change_percentage=50.0,
        current_period_transactions=30,
        previous_period_transactions=20,
        transaction_change_percentage=50.0,
    )
    mock_executor.execute.return_value = ToolExecutionResult(
        status="success", tool="get_sales_trend", data=trend_data
    )

    orchestrator = AnalyticsOrchestrator(
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    outcome = await orchestrator.run("Am I selling more than last week?", shop_id, mock_db)

    assert outcome.outcome_type == OutcomeType.ANSWERED
    assert outcome.tool == "get_sales_trend"
    assert outcome.data == trend_data


@pytest.mark.asyncio
async def test_answered_slow_moving_items(mock_llm_client, mock_executor, mock_db):
    shop_id = uuid4()
    mock_llm_client.generate.return_value = LLMResponse(
        text=None,
        tool_calls=[
            NormalizedToolCall(name="get_slow_moving_items", arguments={"period": "this month"})
        ],
    )
    slow_data = GetSlowMovingItemsOutput(
        items=[
            SlowMovingItem(
                product_id=uuid4(),
                product_name="Matchbox",
                units_sold=0,
                current_stock=50,
                unit_price=Decimal("10.00"),
            )
        ],
        count=1,
    )
    mock_executor.execute.return_value = ToolExecutionResult(
        status="success", tool="get_slow_moving_items", data=slow_data
    )

    orchestrator = AnalyticsOrchestrator(
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    outcome = await orchestrator.run("What hasn't sold recently?", shop_id, mock_db)

    assert outcome.outcome_type == OutcomeType.ANSWERED
    assert outcome.tool == "get_slow_moving_items"
    assert outcome.data == slow_data


@pytest.mark.asyncio
async def test_answered_product_price(mock_llm_client, mock_executor, mock_db):
    shop_id = uuid4()
    mock_llm_client.generate.return_value = LLMResponse(
        text=None,
        tool_calls=[
            NormalizedToolCall(name="get_product_price", arguments={"product_name": "Maize Flour"})
        ],
    )
    price_data = GetProductPriceOutput(
        product_id=uuid4(),
        product_name="Maize Flour",
        unit_price=Decimal("195.00"),
        sku="MF-2KG",
    )
    mock_executor.execute.return_value = ToolExecutionResult(
        status="success", tool="get_product_price", data=price_data
    )

    orchestrator = AnalyticsOrchestrator(
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    outcome = await orchestrator.run("How much is maize flour?", shop_id, mock_db)

    assert outcome.outcome_type == OutcomeType.ANSWERED
    assert outcome.tool == "get_product_price"
    assert outcome.data == price_data


@pytest.mark.asyncio
async def test_malformed_response_outcome_no_retry(mock_llm_client, mock_executor, mock_db):
    shop_id = uuid4()
    mock_llm_client.generate.side_effect = LLMResponseFormatError("Malformed JSON payload")

    orchestrator = AnalyticsOrchestrator(
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    outcome = await orchestrator.run("How much did I sell today?", shop_id, mock_db)

    assert outcome.outcome_type == OutcomeType.MALFORMED_RESPONSE
    assert "Malformed JSON payload" in (outcome.message or "")
    assert mock_llm_client.generate.call_count == 1
    mock_executor.execute.assert_not_called()


@pytest.mark.asyncio
async def test_infrastructure_failure_from_executor(mock_llm_client, mock_executor, mock_db):
    shop_id = uuid4()
    mock_llm_client.generate.return_value = LLMResponse(
        tool_calls=[NormalizedToolCall(name="get_sales_summary", arguments={"period": "today"})]
    )
    mock_executor.execute.return_value = ToolExecutionResult(
        status="failure",
        tool="get_sales_summary",
        error=ToolExecutionError(
            error_type="InfrastructureError",
            message="Database connection lost",
        ),
    )

    orchestrator = AnalyticsOrchestrator(
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    outcome = await orchestrator.run("Sales today?", shop_id, mock_db)

    assert outcome.outcome_type == OutcomeType.INFRASTRUCTURE_FAILURE
    assert "Database connection lost" in (outcome.message or "")
    assert mock_llm_client.generate.call_count == 1
    assert mock_executor.execute.call_count == 1


@pytest.mark.asyncio
async def test_schema_validation_exhaustion_preserves_details(
    mock_llm_client, mock_executor, mock_db
):
    shop_id = uuid4()
    resp = LLMResponse(
        tool_calls=[NormalizedToolCall(name="get_sales_summary", arguments={"bad_arg": "invalid"})]
    )
    mock_llm_client.generate.side_effect = [resp, resp]

    mock_executor.execute.return_value = ToolExecutionResult(
        status="failure",
        tool="get_sales_summary",
        error=ToolExecutionError(
            error_type="SchemaValidationError",
            message="Validation error: extra field forbidden",
            details={"field": "bad_arg"},
        ),
    )

    orchestrator = AnalyticsOrchestrator(
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    outcome = await orchestrator.run("Sales today?", shop_id, mock_db)

    assert outcome.outcome_type == OutcomeType.ARGUMENT_VALIDATION_FAILED
    assert outcome.tool == "get_sales_summary"
    assert "extra field forbidden" in (outcome.message or "")
    assert outcome.details == {"field": "bad_arg"}
    assert mock_llm_client.generate.call_count == 2
    assert mock_executor.execute.call_count == 2


@pytest.mark.asyncio
async def test_domain_failure_no_llm_retry(mock_llm_client, mock_executor, mock_db):
    shop_id = uuid4()
    mock_llm_client.generate.return_value = LLMResponse(
        tool_calls=[NormalizedToolCall(name="get_stock_level", arguments={"product_name": "Sugar"})]
    )
    mock_executor.execute.return_value = ToolExecutionResult(
        status="failure",
        tool="get_stock_level",
        error=ToolExecutionError(
            error_type="ProductNotFoundError",
            message="Product not found",
        ),
    )

    orchestrator = AnalyticsOrchestrator(
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    outcome = await orchestrator.run("How much sugar?", shop_id, mock_db)

    assert outcome.outcome_type == OutcomeType.DOMAIN_FAILURE
    assert mock_llm_client.generate.call_count == 1
    assert mock_executor.execute.call_count == 1
