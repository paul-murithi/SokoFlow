import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.example import router as test_router
from app.api.routes import api_router
from app.core.redis import redis_client
from app.utils.errors import (
    InsufficientStockException,
    ResourceAlreadyExistsException,
    ResourceConflictException,
    ResourceNotFoundException,
)
from app.utils.types import LUA_SAVE_SESSION_SCRIPT


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    global LUA_UPDATE_SESSION

    current_dir = os.path.dirname(__file__)
    script_path = os.path.join(current_dir, "fsm", "lua", LUA_SAVE_SESSION_SCRIPT)

    with open(script_path, "r") as f:
        lua_content = f.read()

    LUA_UPDATE_SESSION = redis_client.register_script(lua_content)  # type: ignore

    yield
    await redis_client.aclose()


app = FastAPI(
    title="SokoFlow",
    description="Headless WhatsApp ERP for Kenyan SMEs",
    version="0.1.0",
    lifespan=lifespan,
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


@app.exception_handler(ResourceConflictException)
async def resource_conflict_handler(
    request: Request, exc: ResourceConflictException
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "success": False,
            "error_type": "RESOURCE_CONFLICT",
            "message": exc.message,
        },
    )
