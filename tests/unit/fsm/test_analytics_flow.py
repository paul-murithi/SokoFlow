from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.ai.contracts.execution import ToolExecutionResult
from app.ai.contracts.outcome import AnalyticsOutcome
from app.ai.contracts.tools import (
    GetLowStockItemsOutput,
    GetProductPriceOutput,
    GetSalesSummaryOutput,
    GetStockLevelOutput,
    LowStockItem,
)
from app.ai.executor import ToolExecutor
from app.ai.formatter import AnalyticsFormatter
from app.ai.orchestrator import AnalyticsOrchestrator
from app.core.config import settings
from app.fsm.engine import FSMEngine
from app.fsm.flows.analytics import AnalyticsFlow
from app.fsm.models import (
    MessageKey,
    PendingCallContext,
    PriorCallContext,
    ScoredProductMatch,
    SessionContext,
    SessionState,
    UserSession,
)
from app.fsm.routing_policy import AnalyticsRoutingPolicy
from app.utils.errors import InvalidInputError


@pytest.fixture
def mock_orchestrator():
    orchestrator = MagicMock(spec=AnalyticsOrchestrator)
    orchestrator.run = AsyncMock()
    orchestrator.executor = MagicMock(spec=ToolExecutor)
    orchestrator.executor.execute = AsyncMock()
    return orchestrator


@pytest.mark.asyncio
async def test_analytics_flow_happy_path_answered(mock_orchestrator):
    shop_id = uuid4()
    sales_data = GetSalesSummaryOutput(
        total_revenue=Decimal("15000.00"),
        transaction_count=12,
    )
    mock_orchestrator.run.return_value = AnalyticsOutcome.answered(
        tool="get_sales_summary",
        data=sales_data,
        call={"name": "get_sales_summary", "arguments": {"period": "today"}},
    )

    flow = AnalyticsFlow(
        db_session=object(),
        orchestrator=mock_orchestrator,
        formatter=AnalyticsFormatter(),
    )
    flow.get_shop_id = AsyncMock(return_value=shop_id)

    session = UserSession(
        phone="+254700000999",
        state=SessionState.IDLE,
        context=SessionContext(error_count=1),
    )

    result = await flow.handle_query(session, "How are sales today?")

    assert result.previous_state == SessionState.IDLE
    assert result.new_state == SessionState.IDLE
    assert result.message_key == MessageKey.ANALYTICS_SALES_SUMMARY
    assert session.context.error_count == 0
    assert session.context.last_analytics_call is not None
    assert session.context.last_analytics_call.tool_name == "get_sales_summary"
    assert session.context.last_analytics_call.arguments == {"period": "today"}


@pytest.mark.asyncio
async def test_analytics_flow_no_analytics_intent_raises_invalid_input(mock_orchestrator):
    shop_id = uuid4()
    mock_orchestrator.run.return_value = AnalyticsOutcome.no_analytics_intent()

    flow = AnalyticsFlow(
        db_session=object(),
        orchestrator=mock_orchestrator,
    )
    flow.get_shop_id = AsyncMock(return_value=shop_id)

    session = UserSession(
        phone="+254700000999",
        state=SessionState.IDLE,
        context=SessionContext(error_count=0),
    )

    with pytest.raises(InvalidInputError) as exc_info:
        await flow.handle_query(session, "Some random text")

    assert exc_info.value.message_key == MessageKey.UNKNOWN_INTENT


@pytest.mark.asyncio
async def test_engine_process_message_no_analytics_intent_increments_error_count(
    mock_orchestrator, monkeypatch
):
    monkeypatch.setattr(settings, "groq_api_key", "test_key")
    shop_id = uuid4()
    mock_orchestrator.run.return_value = AnalyticsOutcome.no_analytics_intent()

    engine = FSMEngine(db_session=object())
    engine.analytics_flow.orchestrator = mock_orchestrator
    engine.analytics_flow.get_shop_id = AsyncMock(return_value=shop_id)

    session = UserSession(
        phone="+254700000999",
        state=SessionState.IDLE,
        context=SessionContext(error_count=0),
    )

    result = await engine.process_message(session, "random gibberish query")

    assert result.new_state == SessionState.IDLE
    assert result.context.error_count == 1
    assert result.message_key == MessageKey.UNKNOWN_INTENT


@pytest.mark.asyncio
async def test_engine_process_message_max_invalid_attempts_resets_to_idle(
    mock_orchestrator, monkeypatch
):
    monkeypatch.setattr(settings, "groq_api_key", "test_key")
    shop_id = uuid4()
    mock_orchestrator.run.return_value = AnalyticsOutcome.no_analytics_intent()

    engine = FSMEngine(db_session=object())
    engine.analytics_flow.orchestrator = mock_orchestrator
    engine.analytics_flow.get_shop_id = AsyncMock(return_value=shop_id)

    session = UserSession(
        phone="+254700000999",
        state=SessionState.IDLE,
        context=SessionContext(error_count=2),  # Already 2 errors, max is 3
    )

    result = await engine.process_message(session, "random gibberish query")

    assert result.new_state == SessionState.IDLE
    assert result.context.error_count == 0
    assert result.message_key == MessageKey.TOO_MANY_INVALID


@pytest.mark.asyncio
async def test_analytics_flow_needs_selection_transitions_to_selection_state(mock_orchestrator):
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
    mock_orchestrator.run.return_value = AnalyticsOutcome.needs_selection(
        candidates=[candidate1, candidate2],
        pending_call={"tool_name": "get_stock_level", "arguments": {"product_name": "milk"}},
        tool="get_stock_level",
    )

    flow = AnalyticsFlow(
        db_session=object(),
        orchestrator=mock_orchestrator,
    )
    flow.get_shop_id = AsyncMock(return_value=shop_id)

    session = UserSession(
        phone="+254700000999",
        state=SessionState.IDLE,
        context=SessionContext(error_count=1),
    )

    result = await flow.handle_query(session, "Check stock for milk")

    assert result.previous_state == SessionState.IDLE
    assert result.new_state == SessionState.ANALYTICS_PRODUCT_SELECTION
    assert session.state == SessionState.ANALYTICS_PRODUCT_SELECTION
    assert session.context.error_count == 0
    assert len(session.context.product_candidates) == 2
    assert session.context.pending_analytics_call is not None
    assert session.context.pending_analytics_call.tool_name == "get_stock_level"
    assert result.message_key == MessageKey.PRODUCT_CHOICES


@pytest.mark.asyncio
async def test_handle_product_selection_happy_path(mock_orchestrator):
    shop_id = uuid4()
    product_id = uuid4()
    candidate = ScoredProductMatch(
        id=product_id,
        shop_id=shop_id,
        name="Fresh Milk 500ml",
        sku="FM-500",
        price=Decimal("60.00"),
        similarity_score=0.88,
    )
    stock_data = GetStockLevelOutput(
        product_id=product_id,
        product_name="Fresh Milk 500ml",
        quantity=24,
        low_stock_threshold=5,
        unit_price=Decimal("60.00"),
        is_low_stock=False,
    )
    mock_orchestrator.executor.execute.return_value = ToolExecutionResult(
        status="success",
        tool="get_stock_level",
        data=stock_data,
    )

    flow = AnalyticsFlow(
        db_session=object(),
        orchestrator=mock_orchestrator,
    )
    flow.get_shop_id = AsyncMock(return_value=shop_id)

    session = UserSession(
        phone="+254700000999",
        state=SessionState.ANALYTICS_PRODUCT_SELECTION,
        context=SessionContext(
            product_candidates=[candidate],
            pending_analytics_call=PendingCallContext(
                tool_name="get_stock_level",
                arguments={"product_name": "milk"},
                candidates=[candidate],
            ),
        ),
    )

    result = await flow.handle_product_selection(session, "1")

    assert result.previous_state == SessionState.ANALYTICS_PRODUCT_SELECTION
    assert result.new_state == SessionState.IDLE
    assert session.state == SessionState.IDLE
    assert session.context.pending_analytics_call is None
    assert session.context.product_candidates == []
    assert session.context.last_analytics_call is not None
    assert session.context.last_analytics_call.tool_name == "get_stock_level"
    assert session.context.last_analytics_call.arguments["product_id"] == str(product_id)
    assert result.message_key == MessageKey.ANALYTICS_STOCK_LEVEL
    mock_orchestrator.executor.execute.assert_awaited_once_with(
        tool_name="get_stock_level",
        raw_args={"product_name": "Fresh Milk 500ml", "product_id": str(product_id)},
        shop_id=shop_id,
        db=flow.db_session,
    )


@pytest.mark.asyncio
async def test_handle_product_selection_invalid_choice_increments_error(mock_orchestrator):
    shop_id = uuid4()
    candidate = ScoredProductMatch(
        id=uuid4(),
        shop_id=shop_id,
        name="Fresh Milk 500ml",
        sku="FM-500",
        price=Decimal("60.00"),
        similarity_score=0.88,
    )

    engine = FSMEngine(db_session=object())
    engine.analytics_flow.orchestrator = mock_orchestrator
    engine.analytics_flow.get_shop_id = AsyncMock(return_value=shop_id)

    session = UserSession(
        phone="+254700000999",
        state=SessionState.ANALYTICS_PRODUCT_SELECTION,
        context=SessionContext(
            product_candidates=[candidate],
            pending_analytics_call=PendingCallContext(
                tool_name="get_stock_level",
                arguments={"product_name": "milk"},
                candidates=[candidate],
            ),
            error_count=0,
        ),
    )

    result = await engine.process_message(session, "99")

    assert result.new_state == SessionState.ANALYTICS_PRODUCT_SELECTION
    assert result.context.error_count == 1
    assert result.message_key == MessageKey.INVALID_CHOICE


@pytest.mark.asyncio
async def test_multi_turn_follow_up_passes_prior_context(mock_orchestrator):
    shop_id = uuid4()
    prior = PriorCallContext(
        tool_name="get_sales_summary",
        arguments={"period": "today"},
        timestamp=datetime.now(timezone.utc),
    )
    sales_data = GetSalesSummaryOutput(
        total_revenue=Decimal("12000.00"),
        transaction_count=10,
    )
    mock_orchestrator.run.return_value = AnalyticsOutcome.answered(
        tool="get_sales_summary",
        data=sales_data,
        call={"name": "get_sales_summary", "arguments": {"period": "yesterday"}},
    )

    flow = AnalyticsFlow(
        db_session=object(),
        orchestrator=mock_orchestrator,
    )
    flow.get_shop_id = AsyncMock(return_value=shop_id)

    session = UserSession(
        phone="+254700000999",
        state=SessionState.IDLE,
        context=SessionContext(last_analytics_call=prior),
    )

    result = await flow.handle_query(session, "and yesterday?")

    assert result.message_key == MessageKey.ANALYTICS_SALES_SUMMARY
    mock_orchestrator.run.assert_awaited_once_with(
        message_text="and yesterday?",
        shop_id=shop_id,
        db=flow.db_session,
        prior_context=prior,
    )


@pytest.mark.asyncio
async def test_engine_routing_policy_declines_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "analytics_enabled", False)

    engine = FSMEngine(db_session=object())
    engine.routing_policy = AnalyticsRoutingPolicy(enabled=False)

    session = UserSession(
        phone="+254700000999",
        state=SessionState.IDLE,
        context=SessionContext(error_count=0),
    )

    result = await engine.process_message(session, "How are sales today?")

    assert result.new_state == SessionState.IDLE
    assert result.context.error_count == 1
    assert result.message_key == MessageKey.UNKNOWN_INTENT


@pytest.mark.asyncio
async def test_analytics_flow_provider_unavailable_does_not_increment_error(mock_orchestrator):
    shop_id = uuid4()
    mock_orchestrator.run.return_value = AnalyticsOutcome.provider_unavailable(
        "Groq connection timeout"
    )

    flow = AnalyticsFlow(
        db_session=object(),
        orchestrator=mock_orchestrator,
    )
    flow.get_shop_id = AsyncMock(return_value=shop_id)

    session = UserSession(
        phone="+254700000999",
        state=SessionState.IDLE,
        context=SessionContext(error_count=0),
    )

    result = await flow.handle_query(session, "How are sales today?")

    assert result.new_state == SessionState.IDLE
    assert session.context.error_count == 0
    assert result.message_key == MessageKey.ANALYTICS_PROVIDER_UNAVAILABLE


@pytest.mark.asyncio
async def test_analytics_flow_product_price_happy_path(mock_orchestrator):
    shop_id = uuid4()
    price_data = GetProductPriceOutput(
        product_id=uuid4(),
        product_name="Maize Flour 2kg",
        unit_price=Decimal("195.00"),
        sku="MF-2KG",
    )
    mock_orchestrator.run.return_value = AnalyticsOutcome.answered(
        tool="get_product_price",
        data=price_data,
        call={"name": "get_product_price", "arguments": {"product_name": "Maize Flour 2kg"}},
    )

    flow = AnalyticsFlow(
        db_session=object(),
        orchestrator=mock_orchestrator,
        formatter=AnalyticsFormatter(),
    )
    flow.get_shop_id = AsyncMock(return_value=shop_id)

    session = UserSession(
        phone="+254700000999",
        state=SessionState.IDLE,
        context=SessionContext(error_count=0),
    )

    result = await flow.handle_query(session, "How much is maize flour 2kg?")

    assert result.new_state == SessionState.IDLE
    assert result.message_key == MessageKey.ANALYTICS_PRODUCT_PRICE
    assert result.message_params["product_name"] == "Maize Flour 2kg"
    assert result.message_params["price"] == "195.00"
    assert session.context.last_analytics_call.tool_name == "get_product_price"


@pytest.mark.asyncio
async def test_analytics_flow_low_stock_items_happy_path(mock_orchestrator):
    shop_id = uuid4()
    low_stock_data = GetLowStockItemsOutput(
        items=[
            LowStockItem(
                product_id=uuid4(),
                product_name="Milk 500ml",
                current_stock=2,
                low_stock_threshold=5,
            )
        ],
        count=1,
    )
    mock_orchestrator.run.return_value = AnalyticsOutcome.answered(
        tool="get_low_stock_items",
        data=low_stock_data,
        call={"name": "get_low_stock_items", "arguments": {}},
    )

    flow = AnalyticsFlow(
        db_session=object(),
        orchestrator=mock_orchestrator,
        formatter=AnalyticsFormatter(),
    )
    flow.get_shop_id = AsyncMock(return_value=shop_id)

    session = UserSession(
        phone="+254700000999",
        state=SessionState.IDLE,
        context=SessionContext(),
    )

    result = await flow.handle_query(session, "Which items are running low on stock?")

    assert result.new_state == SessionState.IDLE
    assert result.message_key == MessageKey.ANALYTICS_LOW_STOCK_ITEMS
    assert result.message_params["count"] == 1


@pytest.mark.asyncio
async def test_handle_product_selection_for_product_price(mock_orchestrator):
    shop_id = uuid4()
    product_id = uuid4()
    candidate = ScoredProductMatch(
        id=product_id,
        shop_id=shop_id,
        name="Maize Flour 2kg",
        sku="MF-2KG",
        price=Decimal("195.00"),
        similarity_score=0.90,
    )
    price_data = GetProductPriceOutput(
        product_id=product_id,
        product_name="Maize Flour 2kg",
        unit_price=Decimal("195.00"),
        sku="MF-2KG",
    )
    mock_orchestrator.executor.execute.return_value = ToolExecutionResult(
        status="success",
        tool="get_product_price",
        data=price_data,
    )

    flow = AnalyticsFlow(
        db_session=object(),
        orchestrator=mock_orchestrator,
    )
    flow.get_shop_id = AsyncMock(return_value=shop_id)

    session = UserSession(
        phone="+254700000999",
        state=SessionState.ANALYTICS_PRODUCT_SELECTION,
        context=SessionContext(
            product_candidates=[candidate],
            pending_analytics_call=PendingCallContext(
                tool_name="get_product_price",
                arguments={"product_name": "flour"},
                candidates=[candidate],
            ),
        ),
    )

    result = await flow.handle_product_selection(session, "1")

    assert result.new_state == SessionState.IDLE
    assert result.message_key == MessageKey.ANALYTICS_PRODUCT_PRICE
    assert session.context.last_analytics_call.tool_name == "get_product_price"
    assert session.context.last_analytics_call.arguments["product_id"] == str(product_id)
