import random
import string
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.schemas.product import ProductCreate
from app.utils.errors import ResourceNotFound


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
            raise HTTPException(
                status_code=409,
                detail="Duplicate. A product with this SKU already exists.",
            )

        return product

    async def get_product(self, product_id: UUID, db: AsyncSession) -> Product | None:
        product = await db.get(Product, product_id)

        if not product:
            raise ResourceNotFound(name="Product", id=str(product_id))

        return product

    def list_products(self) -> None:
        pass

    def update_product(self) -> None:
        pass

    def delete_product(self) -> None:
        pass
