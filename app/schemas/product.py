from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORMBaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProductCreate(ORMBaseSchema):
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
    name: str | None = Field(default=None, min_length=1)
    price: Decimal | None = None

    @field_validator("name")
    @classmethod
    def name_cannot_be_null(cls, value):
        if value is None:
            raise ValueError("name cannot be null")
        return value


class ProductResponse(ORMBaseSchema):
    id: UUID
    name: str
    price: Decimal
    sku: str
