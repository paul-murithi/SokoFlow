from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Inventory


class InventoryService:
    async def add_stock(
        self, product_id: UUID, quantity: int, db: AsyncSession
    ) -> Inventory:
        inventory = await db.scalar(
            select(Inventory).where(Inventory.product_id == product_id)
        )

        if inventory:
            inventory.quantity += quantity
        else:
            inventory = Inventory(product_id=product_id, quantity=quantity)
            db.add(inventory)

        await db.commit()
        await db.refresh(inventory)

        # TODO: Add error handling
        return inventory

    def remove_stock(self) -> None:
        pass

    def get_stock(self) -> None:
        pass

    def is_low_stock(self) -> None:
        pass

    def update_threshold(self) -> None:
        pass
