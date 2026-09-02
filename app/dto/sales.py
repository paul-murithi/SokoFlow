from dataclasses import dataclass
from decimal import Decimal
from typing import Self
from uuid import UUID

from sqlalchemy.engine import RowMapping


@dataclass(frozen=True)
class TopProductByUnits:
    product_id: UUID
    name: str
    units_sold: int

    @classmethod
    def from_row(cls, row: RowMapping) -> Self:
        return cls(product_id=row.product_id, name=row.name, units_sold=row.units_sold)


@dataclass(frozen=True)
class TopProductByRevenue:
    product_id: UUID
    name: str
    revenue: Decimal

    @classmethod
    def from_row(cls, row: RowMapping) -> Self:
        return cls(product_id=row.product_id, name=row.name, revenue=row.revenue)


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
