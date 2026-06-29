from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SaleCreate(BaseModel):
    shop_id: UUID
    product_id: UUID
    quantity: int = Field(gt=0)
    recorded_by: str = "System"


class SaleResponse(BaseModel):
    id: UUID
    shop_id: UUID
    product_id: UUID
    quantity: int
    unit_price: Decimal
    total: Decimal
    recorded_by: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TopProductUnitsInfo(BaseModel):
    product_id: UUID
    units_sold: int


class TopProductRevenueInfo(BaseModel):
    product_id: UUID
    revenue: Decimal


class DailySummaryResponse(BaseModel):
    total_revenue: Decimal
    transaction_count: int
    top_product_by_units: TopProductUnitsInfo | None = None
    top_product_by_revenue: TopProductRevenueInfo | None = None
