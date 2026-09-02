from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.dto.sales import LowStockProductDTO


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
    name: str
    units_sold: int


class TopProductRevenueInfo(BaseModel):
    product_id: UUID
    name: str
    revenue: Decimal


class DailySummaryResponse(BaseModel):
    total_revenue: Decimal
    transaction_count: int
    top_products_by_units: list[TopProductUnitsInfo] = Field(default_factory=list)
    top_products_by_revenue: list[TopProductRevenueInfo] = Field(default_factory=list)
    products_with_low_stock: list[LowStockProductDTO] = Field(default_factory=list)


class SaleResult(BaseModel):
    sale: SaleResponse
    remaining_stock: int
    entered_low_stock: bool
