from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateInventory(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0)


class AddStockRequest(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0)


class DeductStockRequest(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0)


class UpdateThresholdRequest(BaseModel):
    low_stock_threshold: int = Field(ge=0)


class InventoryResponse(BaseModel):
    id: UUID
    product_id: UUID
    quantity: int
    low_stock_threshold: int

    model_config = ConfigDict(from_attributes=True)
