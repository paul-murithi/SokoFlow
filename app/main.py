from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.utils.errors import ResourceNotFound

app = FastAPI(
    title="SokoFlow",
    description="Headless WhatsApp ERP for Kenyan SMEs",
    version="0.1.0",
)


app.include_router(api_router)


@app.exception_handler(ResourceNotFound)
async def resource_not_found_handler(
    request: Request, exc: ResourceNotFound
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": f"{exc.name} with ID {exc.id} not found"},
    )
