from fastapi import APIRouter

from .health import router as health_router
from .products import router as products_router
from .shops import router as shop_router

api_router = APIRouter()

api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(products_router, prefix="/products", tags=["products"])
api_router.include_router(shop_router, prefix="/shops", tags=["shops"])
