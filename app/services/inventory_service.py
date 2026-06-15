from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Inventory


class InventoryService:
    async def add_stock(
        self, product_id: UUID, quantity: int, db: AsyncSession
    ) -> Inventory:
        # TODO: Check if the product exist. If exists, update. If not, add.
        inventory = Inventory(product_id=product_id, quantity=quantity)

        # TODO: Add error handling
        db.add(inventory)
        await db.commit()
        await db.refresh(inventory)

        return inventory

    def remove_stock(self) -> None:
        pass

    def get_stock(self) -> None:
        pass

    def is_low_stock(self) -> None:
        pass

    def update_threshold(self) -> None:
        pass
