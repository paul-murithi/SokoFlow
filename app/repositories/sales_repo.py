from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dto.sales import (
    LowStockProductDTO,
    RevenueSummary,
    TopProductByRevenue,
    TopProductByUnits,
)
from app.sql import load_sql
from app.sql.queries import SalesSQL


class SalesRepository:
    async def get_total_revenue_and_count(
        self, shop_id: UUID, day_start: datetime, day_end: datetime, db: AsyncSession
    ) -> RevenueSummary:
        stmt = text(load_sql(SalesSQL.GET_TOTAL_REVENUE_AND_COUNT))
        result = await db.execute(
            stmt,
            {
                "shop_id": shop_id,
                "day_start": day_start,
                "day_end": day_end,
            },
        )
        revenue, transaction_count = result.one()

        return RevenueSummary(revenue=revenue, transaction_count=transaction_count)

    async def get_products_with_low_stock(
        self, shop_id: UUID, db: AsyncSession
    ) -> list[LowStockProductDTO]:
        stmt = text(load_sql(SalesSQL.GET_PRODUCTS_WITH_LOW_STOCK))
        result = await db.execute(stmt, {"shop_id": shop_id})
        rows = result.mappings().all()
        return [LowStockProductDTO(**row) for row in rows]

    async def get_top_moving_products(
        self, shop_id: UUID, day_start: datetime, day_end: datetime, db: AsyncSession
    ) -> tuple[list[TopProductByUnits], list[TopProductByRevenue]]:
        params = {
            "shop_id": shop_id,
            "day_start": day_start,
            "day_end": day_end,
        }

        top_units_stmt = text(load_sql(SalesSQL.GET_TOP_MOVING_PRODUCTS_BY_UNITS))
        top_revenue_stmt = text(load_sql(SalesSQL.GET_TOP_MOVING_PRODUCTS_BY_REVENUE))

        units_result = (await db.execute(top_units_stmt, params)).mappings()
        top_unit_rows = units_result.all()

        revenue_result = (await db.execute(top_revenue_stmt, params)).mappings()
        top_revenue_rows = revenue_result.all()

        top_units = [TopProductByUnits.from_row(row) for row in top_unit_rows]
        top_revenue_products = [TopProductByRevenue.from_row(row) for row in top_revenue_rows]

        return top_units, top_revenue_products
