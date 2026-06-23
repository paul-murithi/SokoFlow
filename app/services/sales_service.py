from datetime import datetime, time
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dto.sales import TotalRevenue, TransactionCount
from app.models.product import Product
from app.models.sales import Sale
from app.repositories.sales_repo import SalesRepository
from app.services.inventory_service import InventoryService
from app.utils.errors import ResourceNotFoundException

inventory_service = InventoryService()
sales_repo = SalesRepository()


class SalesService:
    async def record_sale(
        self, shop_id: UUID, product_id: UUID, quantity: int, db: AsyncSession
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
            recorded_by="Paul",
        )

        db.add(sale)
        await db.commit()
        await db.refresh(sale)

        return sale

    async def get_daily_summary(
        self, shop_id: UUID, date: datetime, db: AsyncSession
    ) -> None:
        # total_revenue = await self.get_total_revenue(date=date, db=db)
        # total_transactions = await self.get_transaction_count(date=date, db=db)
        # top_units, top_revenue =
        # await sales_repo.get_top_moving_products(date=date, db=db)

        return None

    async def get_total_revenue(self, date: datetime, db: AsyncSession) -> TotalRevenue:
        revenue_stmt = select(func.sum(Sale.total)).where(
            func.date(Sale.created_at) == date.today()
        )
        revenue_result = await db.scalar(revenue_stmt)
        total = revenue_result if revenue_result is not None else Decimal("0")

        return TotalRevenue(total=total)

    async def get_transaction_count(
        self, date: datetime, db: AsyncSession
    ) -> TransactionCount:
        today_start = datetime.combine(date.today(), time.min)
        today_end = datetime.combine(date.today(), time.max)

        transaction_count_stmt = (
            select(func.count().label("transaction_count"))
            .select_from(Sale)
            .where(Sale.created_at.between(today_start, today_end))
        )

        count = await db.scalar(transaction_count_stmt) or 0

        return TransactionCount(transaction_count=count)
