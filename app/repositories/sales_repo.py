from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dto.sales import TopProductByRevenue, TopProductByUnits
from app.models.sales import Sale


class SalesRepository:
    async def get_top_moving_products(
        self, shop_id: UUID, day_start: datetime, day_end: datetime, db: AsyncSession
    ) -> tuple[TopProductByUnits | None, TopProductByRevenue | None]:
        top_units_stmt = (
            select(Sale.product_id, func.sum(Sale.quantity).label("units_sold"))
            .where(
                Sale.shop_id == shop_id,
                Sale.created_at >= day_start,
                Sale.created_at < day_end,
            )
            .group_by(Sale.product_id)
            .order_by(func.sum(Sale.quantity).desc())
            .limit(1)
        )

        top_revenue_stmt = (
            select(Sale.product_id, func.sum(Sale.total).label("revenue"))
            .where(
                Sale.shop_id == shop_id,
                Sale.created_at >= day_start,
                Sale.created_at < day_end,
            )
            .group_by(Sale.product_id)
            .order_by(func.sum(Sale.total).desc())
            .limit(1)
        )

        units_result = (await db.execute(top_units_stmt)).mappings()
        top_unit_row = units_result.first()

        revenue_result = (await db.execute(top_revenue_stmt)).mappings()
        top_revenue_row = revenue_result.first()

        top_unit = TopProductByUnits.from_row(top_unit_row) if top_unit_row else None
        top_revenue_product = (
            TopProductByRevenue.from_row(top_revenue_row) if top_revenue_row else None
        )

        return top_unit, top_revenue_product