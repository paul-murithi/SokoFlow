from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.example import router as test_router
from app.api.routes import api_router
from app.utils.errors import (
    InsufficientStockException,
    ResourceAlreadyExistsException,
    ResourceNotFoundException,
)

app = FastAPI(
    title="SokoFlow",
    description="Headless WhatsApp ERP for Kenyan SMEs",
    version="0.1.0",
)


app.include_router(api_router)
app.include_router(test_router)


@app.exception_handler(ResourceNotFoundException)
async def resource_not_found_handler(
    request: Request, exc: ResourceNotFoundException
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "success": False,
            "error_type": "RESOURCE_NOT_FOUND",
            "message": exc.message,
            "meta": {"entity": exc.entity_name, "id": str(exc.identifier)},
        },
    )


@app.exception_handler(InsufficientStockException)
async def insufficient_stock_exception_handler(
    request: Request, exc: InsufficientStockException
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error_type": "INSUFFICIENT_STOCK",
            "message": exc.message,
        },
    )


@app.exception_handler(ResourceAlreadyExistsException)
async def resource_already_exists_handler(
    request: Request, exc: ResourceAlreadyExistsException
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "success": False,
            "error_type": "DUPLICATE_RESOURCE",
            "message": exc.message,
            "meta": {
                "entity": exc.entity_name,
                "conflict_field": exc.field_name,
                "conflict_value": str(exc.value),
            },
        },
    )
