from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.product import ProductCreate, ProductResponse
from app.services.product_service import ProductService

router = APIRouter()
service = ProductService()


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    payload: ProductCreate, db: AsyncSession = Depends(get_db)
) -> ProductResponse:
    product = await service.create_product(payload, db)
    return ProductResponse.model_validate(product)


@router.get("")
def get_products() -> None: ...


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID, db: AsyncSession = Depends(get_db)
) -> ProductResponse:
    product = await service.get_product(product_id, db)
    return ProductResponse.model_validate(product)


@router.patch("/{id}")
def update_product(id: UUID) -> None: ...


@router.delete("/{id}")
def delete_product(id: UUID) -> None: ...
