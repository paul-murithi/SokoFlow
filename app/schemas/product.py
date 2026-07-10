from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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

    @model_validator(mode="after")
    def validate_name(self) -> "ProductUpdate":
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("Name cannot be null")
        return self


class ProductResponse(ORMBaseSchema):
    id: UUID
    name: str
    price: Decimal
    sku: str
