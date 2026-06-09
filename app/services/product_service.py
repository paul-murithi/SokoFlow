import random
import string

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.schemas.product import ProductCreate, ProductResponse


class ProductService:
    def generate_sku(self, product_name, length=6) -> str:
        prefix = "".join(word[0].upper()
                         for word in product_name.split() if word)
        suffix = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=length)
        )
        return f"{prefix}-{suffix}"

    async def create_product(self, data: ProductCreate, db: AsyncSession) -> ProductResponse:
        product = Product(
            name=data.name, price=data.price, sku=self.generate_sku(data.name)
        )

        db.add(product)
        await db.commit()
        await db.refresh()

        return product

    def get_product(self) -> None:
        pass

    def list_products(self) -> None:
        pass

    def update_product(self) -> None:
        pass

    def delete_product(self) -> None:
        pass
