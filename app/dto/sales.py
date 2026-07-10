from dataclasses import dataclass
from decimal import Decimal
from typing import Self
from uuid import UUID

from sqlalchemy.engine import RowMapping


@dataclass(frozen=True)
class TopProductByUnits:
    product_id: UUID
    units_sold: int

    @classmethod
    def from_row(cls, row: RowMapping) -> Self:
        return cls(product_id=row.product_id, units_sold=row.units_sold)


@dataclass(frozen=True)
class TopProductByRevenue:
    product_id: UUID
    revenue: Decimal

    @classmethod
    def from_row(cls, row: RowMapping) -> Self:
        return cls(product_id=row.product_id, revenue=row.revenue)


@dataclass
class SalesSummary:
    total_revenue: float
    transaction_count: int
    top_product_by_units: TopProductByUnits | None
    top_product_by_revenue: TopProductByRevenue | None


@dataclass(frozen=True)
class TotalRevenue:
    total: Decimal


@dataclass(frozen=True)
class TransactionCount:
    transaction_count: int


@dataclass(frozen=True)
class RevenueSummary:
    revenue: Decimal
    transaction_count: int


@dataclass(frozen=True)
class LowStockProductDTO:
    id: UUID
    name: str
    quantity: int
    low_stock_threshold: int
