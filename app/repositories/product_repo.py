from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.sql import load_sql
from app.sql.queries import ProductSQL


class ProductRepository:
    async def list_products(self, shop_id: UUID, db: AsyncSession) -> list[Product]:
        stmt = select(Product).from_statement(text(load_sql(ProductSQL.LIST_BY_SHOP)))
        result = await db.scalars(stmt, {"shop_id": shop_id})
        return list(result.all())
