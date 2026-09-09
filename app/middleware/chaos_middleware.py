import asyncio
import logging
import random

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.config import settings

logger = logging.getLogger(__name__)


class ChaosMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware for probabilistic failure injection in development/local environments."""

    def __init__(
        self,
        app: ASGIApp,
        enabled: bool = False,
        probability: float = 0.05,
        scenarios: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.probability = probability
        self.scenarios = scenarios or ["latency_injection", "error_injection"]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Respect development / local environment only (not production)
        is_dev = getattr(settings, "environment", "development").lower() in (
            "development",
            "local",
            "test",
            "dev",
        )
        if not self.enabled or not is_dev:
            return await call_next(request)

        # Probabilistic failure injection
        if random.random() < self.probability:
            selected_scenario = random.choice(self.scenarios)
            correlation_id = request.headers.get("X-Correlation-ID", "unknown")
            logger.warning(
                f"[CHAOS MIDDLEWARE] Injecting scenario '{selected_scenario}' on path {request.url.path} [correlation_id={correlation_id}]"
            )

            if selected_scenario == "latency_injection":
                # Injects artificial latency in request path
                await asyncio.sleep(random.uniform(0.5, 2.0))
            elif selected_scenario == "error_injection":
                # Injects error without breaking schema structure
                return JSONResponse(
                    status_code=503,
                    content={
                        "detail": "Chaos middleware injected service temporary unavailability",
                        "correlation_id": correlation_id,
                    },
                )

        return await call_next(request)
