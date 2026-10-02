"""Sales and Revenue Tool Handlers.

Executes get_sales_summary, get_top_products, and get_sales_trend using
existing SokoFlow services and repositories.
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts.tools import (
    GetSalesSummaryInput,
    GetSalesSummaryOutput,
    GetSalesTrendInput,
    GetSalesTrendOutput,
    GetTopProductsInput,
    GetTopProductsOutput,
    RankingDimension,
    TopProductItem,
)
from app.ai.handlers.utils import resolve_period_boundaries, resolve_previous_period_boundaries
from app.repositories.sales_repo import SalesRepository

sales_repo = SalesRepository()


async def handle_get_sales_summary(
    shop_id: UUID,
    input_data: GetSalesSummaryInput,
    db: AsyncSession,
) -> GetSalesSummaryOutput:
    """Calculates total revenue and transaction count for a shop over the period.

    Zero sales is a valid output (total_revenue=0, transaction_count=0), not an error.
    """
    utc_start, utc_end = resolve_period_boundaries(input_data.period)
    summary = await sales_repo.get_total_revenue_and_count(
        shop_id=shop_id,
        day_start=utc_start,
        day_end=utc_end,
        db=db,
    )
    return GetSalesSummaryOutput(
        total_revenue=summary.revenue or Decimal("0.00"),
        transaction_count=summary.transaction_count or 0,
    )


async def handle_get_top_products(
    shop_id: UUID,
    input_data: GetTopProductsInput,
    db: AsyncSession,
) -> GetTopProductsOutput:
    """Returns top product rankings by units and/or revenue for a shop over the period.

    If ranking_dimension is omitted, returns both rankings separately.
    If limit is omitted, backend uses default limit (5).
    """
    limit = input_data.limit or 5
    utc_start, utc_end = resolve_period_boundaries(input_data.period)

    top_units_rows, top_rev_rows = await sales_repo.get_top_moving_products(
        shop_id=shop_id,
        day_start=utc_start,
        day_end=utc_end,
        db=db,
    )

    units_output = None
    if input_data.ranking_dimension in (None, RankingDimension.UNITS):
        units_output = [
            TopProductItem(
                product_id=row.product_id,
                name=row.name,
                units_sold=row.units_sold,
            )
            for row in top_units_rows[:limit]
        ]

    revenue_output = None
    if input_data.ranking_dimension in (None, RankingDimension.REVENUE):
        revenue_output = [
            TopProductItem(
                product_id=row.product_id,
                name=row.name,
                revenue=row.revenue,
            )
            for row in top_rev_rows[:limit]
        ]

    return GetTopProductsOutput(
        units=units_output,
        revenue=revenue_output,
    )


async def handle_get_sales_trend(
    shop_id: UUID,
    input_data: GetSalesTrendInput,
    db: AsyncSession,
) -> GetSalesTrendOutput:
    """Compares sales performance between current and comparison reporting periods."""
    curr_start, curr_end = resolve_period_boundaries(input_data.period)

    if input_data.comparison_period:
        prev_start, prev_end = resolve_period_boundaries(input_data.comparison_period)
    else:
        prev_start, prev_end = resolve_previous_period_boundaries(input_data.period)

    curr_summary = await sales_repo.get_total_revenue_and_count(
        shop_id=shop_id, day_start=curr_start, day_end=curr_end, db=db
    )
    prev_summary = await sales_repo.get_total_revenue_and_count(
        shop_id=shop_id, day_start=prev_start, day_end=prev_end, db=db
    )

    curr_rev = curr_summary.revenue or Decimal("0.00")
    prev_rev = prev_summary.revenue or Decimal("0.00")
    curr_tx = curr_summary.transaction_count or 0
    prev_tx = prev_summary.transaction_count or 0

    rev_change = (
        float((curr_rev - prev_rev) / prev_rev * 100)
        if prev_rev > 0
        else (100.0 if curr_rev > 0 else 0.0)
    )
    tx_change = (
        float((curr_tx - prev_tx) / prev_tx * 100)
        if prev_tx > 0
        else (100.0 if curr_tx > 0 else 0.0)
    )

    return GetSalesTrendOutput(
        current_period_revenue=curr_rev,
        previous_period_revenue=prev_rev,
        revenue_change_percentage=round(rev_change, 2),
        current_period_transactions=curr_tx,
        previous_period_transactions=prev_tx,
        transaction_change_percentage=round(tx_change, 2),
    )
