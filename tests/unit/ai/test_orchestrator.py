from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.ai.contracts.llm import LLMResponse, NormalizedToolCall
from app.ai.contracts.outcome import OutcomeType
from app.ai.contracts.tools import (
    GetSalesSummaryOutput,
    GetTopProductsOutput,
)
from app.ai.errors import LLMProviderTimeoutError
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

    outcome = await orchestrator.run(
        "and yesterday?", shop_id, mock_db, prior_context=prior
    )

    assert outcome.outcome_type == OutcomeType.ANSWERED
    # Verify that prior context was sent to generate
    calls = mock_llm_client.generate.call_args
    messages_passed = calls.kwargs["messages"]
    assert len(messages_passed) == 2
    assert messages_passed[0].role == "assistant"
    assert "Previous tool executed: get_sales_summary" in messages_passed[0].content
    assert messages_passed[1].role == "user"
    assert messages_passed[1].content == "and yesterday?"
