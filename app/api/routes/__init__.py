from fastapi import APIRouter

from .health import router as health_router
from .inventory import router as inventory_router
from .products import router as products_router
from .reports import router as reports_router
from .sales import router as sales_router
from .shops import router as shop_router
from .webhook import router as webhook_router

api_router = APIRouter()

api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(inventory_router, prefix="/inventory", tags=["inventory"])
api_router.include_router(products_router, prefix="/products", tags=["products"])
api_router.include_router(reports_router, prefix="/reports", tags=["reports"])
api_router.include_router(sales_router, prefix="/sales", tags=["sales"])
api_router.include_router(shop_router, prefix="/shops", tags=["shops"])
api_router.include_router(webhook_router, prefix="/webhook", tags=["webhook"])
