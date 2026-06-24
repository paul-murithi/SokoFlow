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
    ) -> tuple[Inventory, bool]:
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
        old_is_low = inventory.quantity <= inventory.low_stock_threshold

        inventory.quantity -= quantity

        db.add(inventory)
        await db.commit()
        await db.refresh(inventory)

        new_is_low = inventory.quantity <= inventory.low_stock_threshold

        low_stock_triggered = self.should_send_low_stock_alert(old_is_low, new_is_low)

        return inventory, low_stock_triggered

    async def get_stock(self, product_id: UUID, db: AsyncSession) -> Inventory:
        result = await db.execute(
            select(Inventory).where(Inventory.product_id == product_id)
        )
        inventory = result.scalar_one_or_none()
        if not inventory:
            raise ResourceNotFoundException(
                entity_name="Inventory Product", identifier=product_id
            )
        return inventory

    def is_low_stock(self, quantity_to_deduct: int, current_quantity: int) -> bool:
        return quantity_to_deduct > current_quantity

    def should_send_low_stock_alert(self, old_is_low: bool, new_is_low: bool) -> bool:
        return (old_is_low, new_is_low) == (False, True)

    async def update_threshold(
        self, product_id: UUID, low_stock_threshold: int, db: AsyncSession
    ) -> Inventory:
        inventory = await self.get_stock(product_id, db)
        inventory.low_stock_threshold = low_stock_threshold
        await db.commit()
        await db.refresh(inventory)
        return inventory