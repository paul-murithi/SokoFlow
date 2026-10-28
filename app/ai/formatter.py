"""Analytics Formatter Component.

Pure function mapping typed AnalyticsOutcome objects to SokoFlow presentation contracts:
(MessageKey, message_params).
"""

from decimal import Decimal
from typing import Any

from app.ai.contracts.outcome import AnalyticsOutcome, OutcomeType
from app.fsm.models import MessageKey


def _resolve_period_name(args: dict[str, Any] | None) -> str:
    """Extracts a friendly period description from tool call arguments."""
    if not args or "period" not in args:
        return "the requested period"

    period = args["period"]
    if isinstance(period, str):
        return period

    if isinstance(period, dict):
        if period.get("period_type") == "relative":
            rel = period.get("relative_period", "")
            mapping = {
                "day": "today",
                "week": "this week",
                "month": "this month",
                "year": "this year",
            }
            return mapping.get(rel, f"the requested {rel or 'period'}")
        if period.get("period_type") == "date_range":
            dr = period.get("date_range", {})
            start = dr.get("start_date", "")
            end = dr.get("end_date", "")
            if start and end:
                return f"{start} to {end}"

    return "the requested period"


def _format_sales_summary(outcome: AnalyticsOutcome) -> tuple[MessageKey, dict[str, Any]]:
    period_name = _resolve_period_name(outcome.call.get("arguments") if outcome.call else None)
    data = outcome.data
    total_rev = getattr(data, "total_revenue", 0)
    tx_count = getattr(data, "transaction_count", 0)

    return (
        MessageKey.ANALYTICS_SALES_SUMMARY,
        {
            "period_name": period_name,
            "total_revenue": f"{total_rev:,.2f}",
            "transaction_count": tx_count,
        },
    )


def _format_stock_level(outcome: AnalyticsOutcome) -> tuple[MessageKey, dict[str, Any]]:
    data = outcome.data
    product_name = getattr(data, "product_name", "Product")
    quantity = getattr(data, "quantity", 0)
    price = getattr(data, "unit_price", 0)
    is_low_stock = getattr(data, "is_low_stock", False)
    threshold = getattr(data, "low_stock_threshold", 0)

    if is_low_stock:
        return (
            MessageKey.ANALYTICS_STOCK_LEVEL_LOW,
            {
                "product_name": product_name,
                "quantity": quantity,
                "price": f"{price:,.2f}",
                "threshold": threshold,
            },
        )

    return (
        MessageKey.ANALYTICS_STOCK_LEVEL,
        {
            "product_name": product_name,
            "quantity": quantity,
            "price": f"{price:,.2f}",
        },
    )


def _format_top_products(outcome: AnalyticsOutcome) -> tuple[MessageKey, dict[str, Any]]:
    period_name = _resolve_period_name(outcome.call.get("arguments") if outcome.call else None)
    data = outcome.data
    units = getattr(data, "units", None) or []
    revenue = getattr(data, "revenue", None) or []

    lines = []
    if units:
        lines.append("*By units sold:*")
        for i, item in enumerate(units[:5], start=1):
            lines.append(f"{i}. {item.name} — {item.units_sold} units")

    if revenue:
        if lines:
            lines.append("")
        lines.append("*By revenue:*")
        for i, item in enumerate(revenue[:5], start=1):
            rev_str = f"KES {item.revenue:,.2f}" if item.revenue is not None else "N/A"
            lines.append(f"{i}. {item.name} — {rev_str}")

    return (
        MessageKey.ANALYTICS_TOP_PRODUCTS,
        {
            "period_name": period_name,
            "products_summary": "\n".join(lines) if lines else "No product rankings available.",
        },
    )


def _format_low_stock_items(outcome: AnalyticsOutcome) -> tuple[MessageKey, dict[str, Any]]:
    data = outcome.data
    items = getattr(data, "items", None) or []
    count = getattr(data, "count", len(items))

    lines = [
        f"• {item.product_name}: {item.current_stock} units left "
        f"(threshold: {item.low_stock_threshold})"
        for item in items[:10]
    ]

    return (
        MessageKey.ANALYTICS_LOW_STOCK_ITEMS,
        {
            "count": count,
            "items_summary": "\n".join(lines) if lines else "No items currently below threshold.",
        },
    )


def _format_sales_trend(outcome: AnalyticsOutcome) -> tuple[MessageKey, dict[str, Any]]:
    call_args = outcome.call.get("arguments", {}) if outcome.call else {}
    period_name = _resolve_period_name(call_args)
    comp_arg = call_args.get("comparison_period")
    comparison_period_name = (
        _resolve_period_name({"period": comp_arg}) if comp_arg else "previous equivalent period"
    )

    data = outcome.data
    curr_rev = getattr(data, "current_period_revenue", Decimal("0.00"))
    prev_rev = getattr(data, "previous_period_revenue", Decimal("0.00"))
    rev_change = getattr(data, "revenue_change_percentage", 0.0)
    curr_tx = getattr(data, "current_period_transactions", 0)
    prev_tx = getattr(data, "previous_period_transactions", 0)
    tx_change = getattr(data, "transaction_change_percentage", 0.0)

    rev_sign = "+" if rev_change >= 0 else ""
    tx_sign = "+" if tx_change >= 0 else ""

    return (
        MessageKey.ANALYTICS_SALES_TREND,
        {
            "period_name": period_name,
            "comparison_period_name": comparison_period_name,
            "current_revenue": f"{curr_rev:,.2f}",
            "previous_revenue": f"{prev_rev:,.2f}",
            "revenue_change": f"{rev_sign}{rev_change:.1f}%",
            "current_transactions": curr_tx,
            "previous_transactions": prev_tx,
            "transaction_change": f"{tx_sign}{tx_change:.1f}%",
        },
    )


def _format_slow_moving_items(outcome: AnalyticsOutcome) -> tuple[MessageKey, dict[str, Any]]:
    call_args = outcome.call.get("arguments", {}) if outcome.call else {}
    period_name = _resolve_period_name(call_args)
    data = outcome.data
    items = getattr(data, "items", None) or []
    count = getattr(data, "count", len(items))

    lines = [
        f"• {item.product_name}: {item.units_sold} sold ({item.current_stock} in stock)"
        for item in items[:10]
    ]

    return (
        MessageKey.ANALYTICS_SLOW_MOVING_ITEMS,
        {
            "period_name": period_name,
            "count": count,
            "items_summary": "\n".join(lines) if lines else "No slow-moving products identified.",
        },
    )


def _format_product_price(outcome: AnalyticsOutcome) -> tuple[MessageKey, dict[str, Any]]:
    data = outcome.data
    product_name = getattr(data, "product_name", "Product")
    price = getattr(data, "unit_price", Decimal("0.00"))
    sku = getattr(data, "sku", "N/A")

    return (
        MessageKey.ANALYTICS_PRODUCT_PRICE,
        {
            "product_name": product_name,
            "price": f"{price:,.2f}",
            "sku": sku,
        },
    )


class AnalyticsFormatter:
    """Maps complete typed AnalyticsOutcome objects to (MessageKey, message_params)."""

    @staticmethod
    def format_outcome(outcome: AnalyticsOutcome) -> tuple[MessageKey, dict[str, Any]]:
        """Pure function converting an AnalyticsOutcome into presentation contracts."""
        match outcome.outcome_type:
            case OutcomeType.ANSWERED:
                if outcome.tool == "get_sales_summary":
                    return _format_sales_summary(outcome)
                if outcome.tool == "get_stock_level":
                    return _format_stock_level(outcome)
                if outcome.tool == "get_top_products":
                    return _format_top_products(outcome)
                if outcome.tool == "get_low_stock_items":
                    return _format_low_stock_items(outcome)
                if outcome.tool == "get_sales_trend":
                    return _format_sales_trend(outcome)
                if outcome.tool == "get_slow_moving_items":
                    return _format_slow_moving_items(outcome)
                if outcome.tool == "get_product_price":
                    return _format_product_price(outcome)
                return (
                    MessageKey.UNKNOWN_ERROR,
                    {"message": f"Tool '{outcome.tool}' executed successfully."},
                )

            case OutcomeType.ANSWERED_EMPTY:
                period_name = _resolve_period_name(
                    outcome.call.get("arguments") if outcome.call else None
                )
                if outcome.tool == "get_top_products":
                    return (
                        MessageKey.ANALYTICS_TOP_PRODUCTS_EMPTY,
                        {"period_name": period_name},
                    )
                if outcome.tool == "get_low_stock_items":
                    return (MessageKey.ANALYTICS_LOW_STOCK_ITEMS_EMPTY, {})
                if outcome.tool == "get_sales_trend":
                    return (
                        MessageKey.ANALYTICS_SALES_TREND_EMPTY,
                        {"period_name": period_name},
                    )
                if outcome.tool == "get_slow_moving_items":
                    return (
                        MessageKey.ANALYTICS_SLOW_MOVING_ITEMS_EMPTY,
                        {"period_name": period_name},
                    )
                return (
                    MessageKey.ANALYTICS_SALES_SUMMARY_EMPTY,
                    {"period_name": period_name},
                )

            case OutcomeType.NEEDS_SELECTION:
                return (
                    MessageKey.PRODUCT_CHOICES,
                    {"candidates": [c.model_dump() for c in outcome.candidates]},
                )

            case (
                OutcomeType.NO_ANALYTICS_INTENT
                | OutcomeType.MALFORMED_RESPONSE
                | OutcomeType.INVALID_PROPOSAL
                | OutcomeType.ARGUMENT_VALIDATION_FAILED
            ):
                return (
                    MessageKey.ANALYTICS_INVALID_PROPOSAL,
                    {"message": outcome.message or ""},
                )

            case OutcomeType.DOMAIN_FAILURE:
                if outcome.error_type == "ProductNotFoundError":
                    return (MessageKey.PRODUCT_NOT_FOUND, {})
                return (
                    MessageKey.ANALYTICS_DOMAIN_ERROR,
                    {"message": outcome.message or "Could not complete analytics request."},
                )

            case OutcomeType.PROVIDER_UNAVAILABLE:
                return (MessageKey.ANALYTICS_PROVIDER_UNAVAILABLE, {})

            case OutcomeType.INFRASTRUCTURE_FAILURE:
                return (MessageKey.ANALYTICS_INFRASTRUCTURE_ERROR, {})
