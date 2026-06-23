from dataclasses import dataclass
from decimal import Decimal
from typing import Self

from sqlalchemy.engine import RowMapping


@dataclass(frozen=True)
class TopProductByUnits:
    product_id: int
    units_sold: int

    @classmethod
    def from_row(cls, row: RowMapping) -> Self:
        return cls(product_id=row.product_id, units_sold=row.units_sold)


@dataclass(frozen=True)
class TopProductByRevenue:
    product_id: int
    revenue: Decimal

    @classmethod
    def from_row(cls, row: RowMapping) -> Self:
        return cls(product_id=row.product_id, revenue=row.revenue)


@dataclass(frozen=True)
class TotalRevenue:
    total: Decimal


@dataclass(frozen=True)
class TransactionCount:
    transaction_count: int
