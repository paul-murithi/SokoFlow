"""Unit tests for pure AnalyticsFormatter presentation logic."""

from decimal import Decimal
from uuid import uuid4

from app.ai.contracts.outcome import AnalyticsOutcome
from app.ai.contracts.tools import (
    GetSalesSummaryOutput,
    GetStockLevelOutput,
    GetTopProductsOutput,
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
    assert key == MessageKey.UNKNOWN_INTENT


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
