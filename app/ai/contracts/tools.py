"""Structured Input and Output Contracts for AI Tools.

All input models enforce extra="forbid" to prevent unexpected or LLM-injected
fields (such as shop_id) from bypassing validation boundaries.
"""

from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.ai.contracts.period import ReportingPeriod


# get_sales_summary
class GetSalesSummaryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: ReportingPeriod = Field(
        ..., description="The reporting period for which to calculate total sales summary."
    )


class GetSalesSummaryOutput(BaseModel):
    total_revenue: Decimal = Field(..., description="Total revenue earned in the period.")
    transaction_count: int = Field(..., description="Total number of completed sale transactions.")


# get_top_products
class RankingDimension(StrEnum):
    UNITS = "units"
    REVENUE = "revenue"


class GetTopProductsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: ReportingPeriod = Field(
        ..., description="The reporting period for product performance rankings."
    )
    ranking_dimension: RankingDimension | None = Field(
        default=None,
        description="Rank by 'units' or 'revenue'. If omitted, both rankings are returned.",
    )
    limit: int | None = Field(
        default=None,
        gt=0,
        description="Optional maximum number of products per ranking category.",
    )


class TopProductItem(BaseModel):
    product_id: UUID
    name: str
    units_sold: int | None = None
    revenue: Decimal | None = None


class GetTopProductsOutput(BaseModel):
    units: list[TopProductItem] | None = Field(
        default=None, description="Top products ranked by units sold."
    )
    revenue: list[TopProductItem] | None = Field(
        default=None, description="Top products ranked by total revenue."
    )


# get_stock_level
class GetStockLevelInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID = Field(
        ..., description="The resolved UUID of the product whose stock level is requested."
    )


class GetStockLevelOutput(BaseModel):
    product_id: UUID
    product_name: str
    quantity: int
    low_stock_threshold: int
    unit_price: Decimal
    is_low_stock: bool


# get_low_stock_items
class GetLowStockItemsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # No LLM arguments. uses trusted shop context


class LowStockItem(BaseModel):
    product_id: UUID
    product_name: str
    current_stock: int
    low_stock_threshold: int
    unit_price: Decimal | None = None


class GetLowStockItemsOutput(BaseModel):
    items: list[LowStockItem]
    count: int


# get_sales_trend
class TrendMetric(StrEnum):
    REVENUE = "revenue"
    TRANSACTIONS = "transactions"


class GetSalesTrendInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: ReportingPeriod = Field(..., description="Primary reporting period to analyze.")
    comparison_period: ReportingPeriod | None = Field(
        default=None,
        description=(
            "Optional reference period to compare against. Defaults to the previous "
            "calendar period."
        ),
    )


class GetSalesTrendOutput(BaseModel):
    current_period_revenue: Decimal
    previous_period_revenue: Decimal
    revenue_change_percentage: float
    current_period_transactions: int
    previous_period_transactions: int
    transaction_change_percentage: float


# get_slow_moving_items
class GetSlowMovingItemsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: ReportingPeriod = Field(
        ..., description="Reporting period over which to measure product sales activity."
    )
    max_sales_count: int = Field(
        default=0,
        ge=0,
        description="Maximum units sold to consider a product 'slow-moving' (default: 0).",
    )
    limit: int | None = Field(
        default=None,
        gt=0,
        description="Optional limit on the number of slow-moving items returned.",
    )


class SlowMovingItem(BaseModel):
    product_id: UUID
    product_name: str
    units_sold: int
    current_stock: int
    unit_price: Decimal


class GetSlowMovingItemsOutput(BaseModel):
    items: list[SlowMovingItem]
    count: int
