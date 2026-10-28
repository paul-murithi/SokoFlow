"""Unit tests for pure AnalyticsFormatter presentation logic."""

from decimal import Decimal
from uuid import uuid4

from app.ai.contracts.outcome import AnalyticsOutcome
from app.ai.contracts.tools import (
    GetLowStockItemsOutput,
    GetProductPriceOutput,
    GetSalesSummaryOutput,
    GetSalesTrendOutput,
    GetSlowMovingItemsOutput,
    GetStockLevelOutput,
    GetTopProductsOutput,
    LowStockItem,
    SlowMovingItem,
    TopProductItem,
)
from app.ai.formatter import AnalyticsFormatter
from app.fsm.models import MessageKey, ScoredProductMatch
from app.services.localization import render_message


def test_format_sales_summary_answered():
    data = GetSalesSummaryOutput(
        total_revenue=Decimal("15250.00"),
        transaction_count=23,
    )
    outcome = AnalyticsOutcome.answered(
        tool="get_sales_summary",
        data=data,
        call={
            "name": "get_sales_summary",
            "arguments": {"period": {"period_type": "relative", "relative_period": "day"}},
        },
    )

    key, params = AnalyticsFormatter.format_outcome(outcome)
    assert key == MessageKey.ANALYTICS_SALES_SUMMARY
    assert params["period_name"] == "today"
    assert params["total_revenue"] == "15,250.00"
    assert params["transaction_count"] == 23

    # Check localization render
    en_text = render_message(key, "en", params)
    assert "KES 15,250.00" in en_text
    assert "today" in en_text
    sw_text = render_message(key, "sw", params)
    assert "KES 15,250.00" in sw_text
    assert "today" in sw_text


def test_format_sales_summary_answered_empty():
    data = GetSalesSummaryOutput(
        total_revenue=Decimal("0.00"),
        transaction_count=0,
    )
    outcome = AnalyticsOutcome.answered_empty(
        tool="get_sales_summary",
        data=data,
        call={
            "name": "get_sales_summary",
            "arguments": {"period": {"period_type": "relative", "relative_period": "month"}},
        },
    )

    key, params = AnalyticsFormatter.format_outcome(outcome)
    assert key == MessageKey.ANALYTICS_SALES_SUMMARY_EMPTY
    assert params["period_name"] == "this month"

    en_text = render_message(key, "en", params)
    assert "No sales were recorded for this month." in en_text


def test_format_stock_level_normal():
    data = GetStockLevelOutput(
        product_id=uuid4(),
        product_name="Sugar 1kg",
        quantity=50,
        low_stock_threshold=10,
        unit_price=Decimal("180.00"),
        is_low_stock=False,
    )
    outcome = AnalyticsOutcome.answered(
        tool="get_stock_level",
        data=data,
        call={"name": "get_stock_level", "arguments": {"product_name": "Sugar"}},
    )

    key, params = AnalyticsFormatter.format_outcome(outcome)
    assert key == MessageKey.ANALYTICS_STOCK_LEVEL
    assert params["product_name"] == "Sugar 1kg"
    assert params["quantity"] == 50
    assert params["price"] == "180.00"

    en_text = render_message(key, "en", params)
    assert "Sugar 1kg" in en_text
    assert "50 units" in en_text


def test_format_stock_level_low_stock():
    data = GetStockLevelOutput(
        product_id=uuid4(),
        product_name="Maize Flour 2kg",
        quantity=3,
        low_stock_threshold=10,
        unit_price=Decimal("150.00"),
        is_low_stock=True,
    )
    outcome = AnalyticsOutcome.answered(
        tool="get_stock_level",
        data=data,
        call={"name": "get_stock_level", "arguments": {"product_name": "Maize Flour"}},
    )

    key, params = AnalyticsFormatter.format_outcome(outcome)
    assert key == MessageKey.ANALYTICS_STOCK_LEVEL_LOW
    assert params["quantity"] == 3
    assert params["threshold"] == 10

    en_text = render_message(key, "en", params)
    assert "Low Stock Warning" in en_text


def test_format_top_products():
    data = GetTopProductsOutput(
        units=[
            TopProductItem(product_id=uuid4(), name="Bread", units_sold=40),
            TopProductItem(product_id=uuid4(), name="Milk", units_sold=25),
        ],
        revenue=[
            TopProductItem(product_id=uuid4(), name="Cooking Oil", revenue=Decimal("5000.00")),
        ],
    )
    outcome = AnalyticsOutcome.answered(
        tool="get_top_products",
        data=data,
        call={
            "name": "get_top_products",
            "arguments": {"period": {"period_type": "relative", "relative_period": "week"}},
        },
    )

    key, params = AnalyticsFormatter.format_outcome(outcome)
    assert key == MessageKey.ANALYTICS_TOP_PRODUCTS
    assert params["period_name"] == "this week"
    assert "Bread" in params["products_summary"]
    assert "Cooking Oil" in params["products_summary"]


def test_format_needs_selection():
    shop_id = uuid4()
    match1 = ScoredProductMatch(
        id=uuid4(),
        shop_id=shop_id,
        name="Sugar 1kg",
        sku="SUG-1",
        price=Decimal("180.00"),
        similarity_score=0.85,
    )
    match2 = ScoredProductMatch(
        id=uuid4(),
        shop_id=shop_id,
        name="Sugar 2kg",
        sku="SUG-2",
        price=Decimal("350.00"),
        similarity_score=0.80,
    )
    outcome = AnalyticsOutcome.needs_selection(
        candidates=[match1, match2],
        pending_call={"tool_name": "get_stock_level", "arguments": {"product_name": "Sugar"}},
    )

    key, params = AnalyticsFormatter.format_outcome(outcome)
    assert key == MessageKey.PRODUCT_CHOICES
    assert len(params["candidates"]) == 2

    en_text = render_message(key, "en", params)
    assert "Sugar 1kg" in en_text
    assert "Sugar 2kg" in en_text


def test_format_no_analytics_intent():
    outcome = AnalyticsOutcome.no_analytics_intent()
    key, params = AnalyticsFormatter.format_outcome(outcome)
    assert key == MessageKey.ANALYTICS_INVALID_PROPOSAL


def test_format_malformed_response():
    outcome = AnalyticsOutcome.malformed_response("Invalid JSON")
    key, params = AnalyticsFormatter.format_outcome(outcome)
    assert key == MessageKey.ANALYTICS_INVALID_PROPOSAL


def test_format_infrastructure_failure():
    outcome = AnalyticsOutcome.infrastructure_failure("DB connection lost")
    key, params = AnalyticsFormatter.format_outcome(outcome)
    assert key == MessageKey.ANALYTICS_INFRASTRUCTURE_ERROR


def test_format_invalid_proposal():
    outcome = AnalyticsOutcome.invalid_proposal("Unknown tool")
    key, params = AnalyticsFormatter.format_outcome(outcome)
    assert key == MessageKey.ANALYTICS_INVALID_PROPOSAL


def test_format_domain_failure_product_not_found():
    outcome = AnalyticsOutcome.domain_failure(
        tool="get_stock_level",
        error_type="ProductNotFoundError",
        message="Product not found",
    )
    key, params = AnalyticsFormatter.format_outcome(outcome)
    assert key == MessageKey.PRODUCT_NOT_FOUND


def test_format_provider_unavailable():
    outcome = AnalyticsOutcome.provider_unavailable("Timeout")
    key, params = AnalyticsFormatter.format_outcome(outcome)
    assert key == MessageKey.ANALYTICS_PROVIDER_UNAVAILABLE


def test_format_low_stock_items_answered():
    items = [
        LowStockItem(
            product_id=uuid4(),
            product_name="Sugar 1kg",
            current_stock=2,
            low_stock_threshold=5,
        ),
        LowStockItem(
            product_id=uuid4(),
            product_name="Cooking Oil 500ml",
            current_stock=1,
            low_stock_threshold=3,
        ),
    ]
    data = GetLowStockItemsOutput(items=items, count=2)
    outcome = AnalyticsOutcome.answered(
        tool="get_low_stock_items",
        data=data,
        call={"name": "get_low_stock_items", "arguments": {}},
    )

    key, params = AnalyticsFormatter.format_outcome(outcome)
    assert key == MessageKey.ANALYTICS_LOW_STOCK_ITEMS
    assert params["count"] == 2
    assert "Sugar 1kg" in params["items_summary"]

    en_text = render_message(key, "en", params)
    assert "Low Stock Alert" in en_text
    assert "Sugar 1kg" in en_text


def test_format_low_stock_items_empty():
    data = GetLowStockItemsOutput(items=[], count=0)
    outcome = AnalyticsOutcome.answered_empty(
        tool="get_low_stock_items",
        data=data,
        call={"name": "get_low_stock_items", "arguments": {}},
    )

    key, params = AnalyticsFormatter.format_outcome(outcome)
    assert key == MessageKey.ANALYTICS_LOW_STOCK_ITEMS_EMPTY
    en_text = render_message(key, "en", params)
    assert "well-stocked" in en_text


def test_format_sales_trend_answered():
    data = GetSalesTrendOutput(
        current_period_revenue=Decimal("15000.00"),
        previous_period_revenue=Decimal("10000.00"),
        revenue_change_percentage=50.0,
        current_period_transactions=30,
        previous_period_transactions=20,
        transaction_change_percentage=50.0,
    )
    outcome = AnalyticsOutcome.answered(
        tool="get_sales_trend",
        data=data,
        call={
            "name": "get_sales_trend",
            "arguments": {"period": {"period_type": "relative", "relative_period": "week"}},
        },
    )

    key, params = AnalyticsFormatter.format_outcome(outcome)
    assert key == MessageKey.ANALYTICS_SALES_TREND
    assert params["period_name"] == "this week"
    assert params["revenue_change"] == "+50.0%"

    en_text = render_message(key, "en", params)
    assert "KES 15,000.00" in en_text
    assert "+50.0%" in en_text


def test_format_sales_trend_empty():
    data = GetSalesTrendOutput(
        current_period_revenue=Decimal("0.00"),
        previous_period_revenue=Decimal("0.00"),
        revenue_change_percentage=0.0,
        current_period_transactions=0,
        previous_period_transactions=0,
        transaction_change_percentage=0.0,
    )
    outcome = AnalyticsOutcome.answered_empty(
        tool="get_sales_trend",
        data=data,
        call={
            "name": "get_sales_trend",
            "arguments": {"period": {"period_type": "relative", "relative_period": "month"}},
        },
    )

    key, params = AnalyticsFormatter.format_outcome(outcome)
    assert key == MessageKey.ANALYTICS_SALES_TREND_EMPTY
    en_text = render_message(key, "en", params)
    assert "No sales activity recorded" in en_text


def test_format_slow_moving_items_answered():
    items = [
        SlowMovingItem(
            product_id=uuid4(),
            product_name="Bar Soap",
            units_sold=1,
            current_stock=25,
            unit_price=Decimal("70.00"),
        )
    ]
    data = GetSlowMovingItemsOutput(items=items, count=1)
    outcome = AnalyticsOutcome.answered(
        tool="get_slow_moving_items",
        data=data,
        call={
            "name": "get_slow_moving_items",
            "arguments": {"period": {"period_type": "relative", "relative_period": "month"}},
        },
    )

    key, params = AnalyticsFormatter.format_outcome(outcome)
    assert key == MessageKey.ANALYTICS_SLOW_MOVING_ITEMS
    assert params["count"] == 1
    assert "Bar Soap" in params["items_summary"]

    en_text = render_message(key, "en", params)
    assert "Bar Soap" in en_text


def test_format_slow_moving_items_empty():
    data = GetSlowMovingItemsOutput(items=[], count=0)
    outcome = AnalyticsOutcome.answered_empty(
        tool="get_slow_moving_items",
        data=data,
        call={
            "name": "get_slow_moving_items",
            "arguments": {"period": {"period_type": "relative", "relative_period": "month"}},
        },
    )

    key, params = AnalyticsFormatter.format_outcome(outcome)
    assert key == MessageKey.ANALYTICS_SLOW_MOVING_ITEMS_EMPTY
    en_text = render_message(key, "en", params)
    assert "No slow-moving items" in en_text


def test_format_product_price_answered():
    data = GetProductPriceOutput(
        product_id=uuid4(),
        product_name="Maize Flour 2kg",
        unit_price=Decimal("195.00"),
        sku="MF-2KG",
    )
    outcome = AnalyticsOutcome.answered(
        tool="get_product_price",
        data=data,
        call={"name": "get_product_price", "arguments": {"product_name": "Maize Flour 2kg"}},
    )

    key, params = AnalyticsFormatter.format_outcome(outcome)
    assert key == MessageKey.ANALYTICS_PRODUCT_PRICE
    assert params["product_name"] == "Maize Flour 2kg"
    assert params["price"] == "195.00"
    assert params["sku"] == "MF-2KG"

    en_text = render_message(key, "en", params)
    assert "KES 195.00" in en_text
    assert "MF-2KG" in en_text
    sw_text = render_message(key, "sw", params)
    assert "Bei ya" in sw_text
