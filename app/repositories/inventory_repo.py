from typing import cast
from uuid import UUID

from sqlalchemy import ScalarResult, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Inventory
from app.sql import load_sql
from app.sql.queries import InventorySQL


class InventoryRepository:
    async def add_stock(self, product_id: UUID, quantity: int, db: AsyncSession) -> Inventory:
        stmt = select(Inventory).from_statement(text(load_sql(InventorySQL.ADD_STOCK)))
        result = cast(
            ScalarResult[Inventory],
            await db.scalars(stmt, {"product_id": product_id, "quantity": quantity}),
        )

        return result.one()

    async def get_by_product_id(self, product_id: UUID, db: AsyncSession) -> Inventory | None:
        stmt = select(Inventory).from_statement(text(load_sql(InventorySQL.GET_BY_PRODUCT_ID)))
        result = await db.scalars(stmt, {"product_id": product_id})
        return result.one_or_none()
