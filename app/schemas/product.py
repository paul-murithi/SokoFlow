from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator


class ProductCreate(BaseModel):
    name: str
    price: Decimal
    shop_id: UUID

    @field_validator("price")
    @classmethod
    def ensure_positive_price(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("The price must be a positive number")
        return value


class ProductUpdate(BaseModel):
    name: str | None = None
    price: Decimal | None = None


class ProductResponse(BaseModel):
    id: UUID
    name: str
    price: Decimal
    sku: str
