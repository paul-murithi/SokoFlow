from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.sales import Sale
from app.services.inventory_service import InventoryService
from app.utils.errors import ResourceNotFoundException

inventory_service = InventoryService()


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
