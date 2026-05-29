from fastapi import FastAPI

app = FastAPI(
    title="SokoFlow",
    description="Headless WhatsApp ERP for Kenyan SMEs",
    version="0.1.0",
)


@app.get("/health")
async def health() -> dict:
    # TODO (Week 1): expand to check DB + Redis connectivity
    return {"status": "ok", "service": "sokoflow-api"}
