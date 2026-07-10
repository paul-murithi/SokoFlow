from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services.product_service import ProductService

router = APIRouter()
service = ProductService()


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    payload: ProductCreate, db: AsyncSession = Depends(get_db)
) -> ProductResponse:
    product = await service.create_product(payload, db)
    return ProductResponse.model_validate(product)


@router.get("", response_model=list[ProductResponse])
async def list_products(
    shop_id: UUID, db: AsyncSession = Depends(get_db)
) -> list[ProductResponse]:
    products = await service.list_products(shop_id, db)
    return [ProductResponse.model_validate(p) for p in products]


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID, db: AsyncSession = Depends(get_db)
) -> ProductResponse:
    product = await service.get_product(product_id, db)
    return ProductResponse.model_validate(product)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
) -> ProductResponse:
    product = await service.update_product(product_id, payload, db)
    return ProductResponse.model_validate(product)


@router.delete("/{product_id}", status_code=204)
async def delete_product(product_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    await service.delete_product(product_id, db)
