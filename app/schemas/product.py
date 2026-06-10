from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class ProductCreate(BaseModel):
    name: str
    price: Decimal
    shop_id: UUID


class ProductUpdate(BaseModel):
    name: str | None = None
    price: Decimal | None = None


class ProductResponse(BaseModel):
    id: UUID
    name: str
    price: Decimal
    sku: str
