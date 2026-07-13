from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.dto.sales import LowStockProductDTO, RevenueSummary
from app.models.product import Product
from app.models.sales import Sale
from app.repositories.sales_repo import SalesRepository
from app.services.inventory_service import InventoryService
from app.utils.errors import ResourceNotFoundException

inventory_service = InventoryService()
sales_repo = SalesRepository()


class SalesService:
    @staticmethod
    def _local_day_bounds_to_utc(
        date_input: date, local_tz_name: str = "Africa/Nairobi"
    ) -> tuple[datetime, datetime]:
        local_tz = ZoneInfo(local_tz_name)

        local_start = datetime.combine(date_input, time.min, tzinfo=local_tz)
        local_end = local_start + timedelta(days=1)

        utc_start = local_start.astimezone(ZoneInfo("UTC"))
        utc_end = local_end.astimezone(ZoneInfo("UTC"))

        return utc_start, utc_end

    async def record_sale(
        self,
        shop_id: UUID,
        product_id: UUID,
        quantity: int,
        db: AsyncSession,
        recorded_by: str = "Paul",
    ) -> Sale:
        # Load Product
        product = await db.get(Product, product_id)
        if product is None:
            raise ResourceNotFoundException(
                entity_name="Product", identifier=product_id
            )

        # Reduce Inventory
        await inventory_service.deduct_stock(
            product_id=product_id, quantity=quantity, db=db
        )

        # Create Sale
        sale = Sale(
            shop_id=shop_id,
            product_id=product_id,
            quantity=quantity,
            unit_price=product.price,
            recorded_by=recorded_by,
        )

        db.add(sale)
        await db.commit()
        await db.refresh(sale)

        return sale

    async def get_daily_summary(
        self, shop_id: UUID, date: date, db: AsyncSession
    ) -> dict[str, Any]:  # Improve return type
        day_start, day_end = SalesService._local_day_bounds_to_utc(date_input=date)

        revenue_summary = await self.get_total_revenue_and_count(
            date=date, shop_id=shop_id, db=db
        )
        total_revenue = revenue_summary.revenue
        transaction_count = revenue_summary.transaction_count

        top_units, top_revenue = await sales_repo.get_top_moving_products(
            shop_id=shop_id, day_start=day_start, day_end=day_end, db=db
        )

        return {
            "total_revenue": total_revenue,
            "transaction_count": transaction_count,
            "top_product_by_units": {
                "product_id": top_units.product_id,
                "units_sold": top_units.units_sold,
            }
            if top_units
            else None,
            "top_product_by_revenue": {
                "product_id": top_revenue.product_id,
                "revenue": top_revenue.revenue,
            }
            if top_revenue
            else None,
        }

    async def get_total_revenue_and_count(
        self, date: date, shop_id: UUID, db: AsyncSession
    ) -> RevenueSummary:
        day_start, day_end = SalesService._local_day_bounds_to_utc(date_input=date)
        return await sales_repo.get_total_revenue_and_count(
            shop_id=shop_id, day_start=day_start, day_end=day_end, db=db
        )

    async def get_products_with_low_stock(
        self, shop_id: UUID, db: AsyncSession
    ) -> list[LowStockProductDTO]:
        return await sales_repo.get_products_with_low_stock(shop_id=shop_id, db=db)
