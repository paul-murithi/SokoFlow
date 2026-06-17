from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Inventory
from app.utils.errors import InsufficientStockException, ResourceNotFoundException


class InventoryService:
    async def add_stock(
        self, product_id: UUID, quantity: int, db: AsyncSession
    ) -> Inventory:
        # TODO: Concurrency and race condition possibility
        result = await db.execute(
            select(Inventory).where(Inventory.product_id == product_id)
        )
        inventory = result.scalar_one_or_none()

        if inventory:
            inventory.quantity += quantity
        else:
            inventory = Inventory(product_id=product_id, quantity=quantity)
            db.add(inventory)

        await db.commit()
        await db.refresh(inventory)

        # TODO: Add error handling
        return inventory

    async def deduct_stock(
        self, product_id: UUID, quantity: int, db: AsyncSession
    ) -> Inventory:
        result = await db.execute(
            select(Inventory).where(Inventory.product_id == product_id)
        )
        inventory = result.scalar_one_or_none()

        if not inventory:
            raise ResourceNotFoundException(
                entity_name="Inventory Product", identifier=product_id
            )

        if self.is_low_stock(
            quantity_to_deduct=quantity, current_quantity=inventory.quantity
        ):
            raise InsufficientStockException(
                product_id=str(product_id),
                available=inventory.quantity,
                requested=quantity,
            )

        inventory.quantity -= quantity

        db.add(inventory)
        await db.commit()
        await db.refresh(inventory)

        return inventory

    def get_stock(self) -> None:
        pass

    def is_low_stock(self, quantity_to_deduct: int, current_quantity: int) -> bool:
        return quantity_to_deduct > current_quantity

    def update_threshold(self) -> None:
        pass
