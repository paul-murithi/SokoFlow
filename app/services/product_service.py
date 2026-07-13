import random
import string
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.repositories.product_repo import ProductRepository
from app.schemas.product import ProductCreate, ProductUpdate
from app.utils.errors import ResourceAlreadyExistsException, ResourceNotFoundException

product_repo = ProductRepository()


class ProductService:
    def generate_sku(self, product_name: str, length: int = 6) -> str:
        prefix = "".join(word[0].upper() for word in product_name.split() if word)
        suffix = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=length)
        )
        return f"{prefix}-{suffix}"

    async def create_product(self, data: ProductCreate, db: AsyncSession) -> Product:
        product = Product(
            name=data.name,
            price=data.price,
            sku=self.generate_sku(data.name),
            shop_id=data.shop_id,
        )

        db.add(product)
        try:
            await db.commit()
            await db.refresh(product)
            return product
        # TODO: Add more error handlers
        except IntegrityError:
            await db.rollback()
            raise ResourceAlreadyExistsException(
                entity_name="Product", field_name="SKU", value=product.sku
            )

        return product

    async def get_product(self, product_id: UUID, db: AsyncSession) -> Product:
        product = await db.get(Product, product_id)

        if not product:
            raise ResourceNotFoundException(
                entity_name="Product", identifier=product_id
            )

        return product

    async def list_products(self, shop_id: UUID, db: AsyncSession) -> list[Product]:
        result = await product_repo.list_products(shop_id=shop_id, db=db)
        # TODO: Risk of returning thousands of rows. Change to pagination
        return result

    async def update_product(
        self, product_id: UUID, data: ProductUpdate, db: AsyncSession
    ) -> Product:
        product = await self.get_product(product_id, db)
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(product, key, value)

        # Regenerate SKU if name has changed
        if "name" in update_data:
            product.sku = self.generate_sku(update_data["name"])

        try:
            await db.commit()
            await db.refresh(product)
            return product
        except IntegrityError:
            await db.rollback()
            raise ResourceAlreadyExistsException(
                entity_name="Product", field_name="SKU", value=product.sku
            )

    async def delete_product(self, product_id: UUID, db: AsyncSession) -> None:
        product = await self.get_product(product_id, db)
        await db.delete(product)
        await db.commit()
