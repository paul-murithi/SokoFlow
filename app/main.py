from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.example import router as test_router
from app.api.routes import api_router
from app.core.exception_handlers import register_exception_handlers
from app.core.redis import redis_client
from app.fsm.session_lua import register_session_update_script


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    register_session_update_script(redis_client)

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

register_exception_handlers(app)
