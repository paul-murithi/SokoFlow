from fastapi import FastAPI

from app.api.routes import api_router

app = FastAPI(
    title="SokoFlow",
    description="Headless WhatsApp ERP for Kenyan SMEs",
    version="0.1.0",
)


app.include_router(api_router)
