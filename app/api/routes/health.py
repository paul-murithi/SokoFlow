from typing import Any

import redis.asyncio as ioredis
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings

router = APIRouter()


@router.get("")
async def health() -> dict[str, Any]:
    response: dict[str, Any] = {
        "status": "ok",
        "services": {
            "api": "ok",
            "postgres": "unknown",
            "redis": "unknown",
        },
    }

    # Postgres
    try:
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(settings.database_url)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        response["services"]["postgres"] = "ok"
    except Exception as e:
        response["services"]["postgres"] = f"error: {e}"
        response["status"] = "degraded"

    # Redis
    try:
        r = ioredis.from_url(settings.redis_url)
        await r.ping()
        await r.close()
        response["services"]["redis"] = "ok"
    except Exception as e:
        response["services"]["redis"] = f"error: {e}"
        response["status"] = "degraded"

    return response
