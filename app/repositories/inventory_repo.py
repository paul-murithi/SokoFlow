from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Inventory
from app.sql import load_sql
from app.sql.queries import InventorySQL


class InventoryRepository:
    async def get_by_product_id(
        self, product_id: UUID, db: AsyncSession
    ) -> Inventory | None:
        stmt = select(Inventory).from_statement(
            text(load_sql(InventorySQL.GET_BY_PRODUCT_ID))
        )
        result = await db.scalars(stmt, {"product_id": product_id})
        return result.one_or_none()
