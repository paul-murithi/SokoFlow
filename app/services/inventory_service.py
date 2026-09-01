from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Inventory
from app.repositories.inventory_repo import InventoryRepository
from app.schemas.inventory import StockDeductionResult
from app.services.low_stock_notification_service import LowStockNotificationService
from app.utils.errors import InsufficientStockException, ResourceNotFoundException

inventory_repo = InventoryRepository()
low_stock_notification_service = LowStockNotificationService()


class InventoryService:
    async def add_stock(
        self, product_id: UUID, quantity: int, db: AsyncSession, commit: bool = True
    ) -> Inventory:
        # TODO: commit defaults to True,
        # for reuse inside the larger multi step transaction later (FSM)
        inventory = await inventory_repo.add_stock(product_id=product_id, quantity=quantity, db=db)
        return await self._finalize_inventory(inventory, db, commit)

    async def deduct_stock(
        self, product_id: UUID, quantity: int, db: AsyncSession, commit: bool = True
    ) -> StockDeductionResult:
        result = await db.execute(
            select(Inventory).where(Inventory.product_id == product_id).with_for_update()
        )
        inventory = result.scalar_one_or_none()

        if not inventory:
            raise ResourceNotFoundException(entity_name="Inventory Product", identifier=product_id)

        if self.is_insufficient_stock(
            quantity_to_deduct=quantity, current_quantity=inventory.quantity
        ):
            raise InsufficientStockException(
                product_id=str(product_id),
                available=inventory.quantity,
                requested=quantity,
            )
        old_is_low = inventory.quantity <= inventory.low_stock_threshold

        inventory.quantity -= quantity

        inventory = await self._finalize_inventory(inventory, db, commit)

        new_is_low = inventory.quantity <= inventory.low_stock_threshold

        entered_low_stock = self.should_send_low_stock_alert(old_is_low, new_is_low)

        return StockDeductionResult(
            remaining_stock=inventory.quantity, entered_low_stock=entered_low_stock
        )

    async def get_stock(self, product_id: UUID, db: AsyncSession) -> Inventory:
        inventory = await inventory_repo.get_by_product_id(product_id=product_id, db=db)
        if not inventory:
            raise ResourceNotFoundException(entity_name="Inventory Product", identifier=product_id)
        return inventory

    def is_insufficient_stock(self, quantity_to_deduct: int, current_quantity: int) -> bool:
        return quantity_to_deduct > current_quantity

    def should_send_low_stock_alert(self, old_is_low: bool, new_is_low: bool) -> bool:
        return (old_is_low, new_is_low) == (False, True)

    async def update_threshold(
        self,
        product_id: UUID,
        low_stock_threshold: int,
        db: AsyncSession,
        commit: bool = True,
    ) -> Inventory:
        inventory = await self.get_stock(product_id, db)
        inventory.low_stock_threshold = low_stock_threshold
        return await self._finalize_inventory(inventory, db, commit)

    async def _finalize_inventory(
        self, inventory: Inventory, db: AsyncSession, commit: bool
    ) -> Inventory:
        try:
            if commit:
                await db.commit()
            else:
                await db.flush()

            await db.refresh(inventory)
            return inventory
        except Exception:
            if commit:
                await db.rollback()
            raise
