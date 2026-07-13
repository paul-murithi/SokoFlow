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
    ) -> tuple[TopProductByUnits | None, TopProductByRevenue | None]:
        params = {
            "shop_id": shop_id,
            "day_start": day_start,
            "day_end": day_end,
        }

        top_units_stmt = text(load_sql(SalesSQL.GET_TOP_MOVING_PRODUCTS_BY_UNITS))
        top_revenue_stmt = text(load_sql(SalesSQL.GET_TOP_MOVING_PRODUCTS_BY_REVENUE))

        units_result = (await db.execute(top_units_stmt, params)).mappings()
        top_unit_row = units_result.first()

        revenue_result = (await db.execute(top_revenue_stmt, params)).mappings()
        top_revenue_row = revenue_result.first()

        top_unit = TopProductByUnits.from_row(top_unit_row) if top_unit_row else None
        top_revenue_product = (
            TopProductByRevenue.from_row(top_revenue_row) if top_revenue_row else None
        )

        return top_unit, top_revenue_product
