from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.middleware.metrics import PrometheusMiddleware
from app.models.schemas import HealthResponse, ReadinessResponse
from app.routers import inference

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL = os.environ.get("LOG_LEVEL", "info").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="LLM Inference Gateway",
    description=(
        "A cloud-native LLM inference API backed by Google Gemini. "
        "Exposes an OpenAI-compatible /v1/chat endpoint with Prometheus metrics."
    ),
    version="1.0.0",
)

app.add_middleware(PrometheusMiddleware)
app.include_router(inference.router, tags=["Inference"])


# ---------------------------------------------------------------------------
# Health & readiness probes
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["Observability"])
async def health() -> HealthResponse:
    """Liveness probe — always returns 200 if the process is running."""
    return HealthResponse(status="ok")


@app.get("/ready", response_model=ReadinessResponse, tags=["Observability"])
async def ready() -> ReadinessResponse:
    """
    Readiness probe — returns 200 only when the Gemini API key is configured.
    Kubernetes will not route traffic here until this passes.
    """
    key_configured = bool(os.environ.get("GEMINI_API_KEY"))
    if not key_configured:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not configured",
        )
    return ReadinessResponse(status="ok", gemini_key_configured=True)


# ---------------------------------------------------------------------------
# Prometheus metrics scrape endpoint
# ---------------------------------------------------------------------------


@app.get("/metrics", tags=["Observability"], include_in_schema=False)
async def metrics() -> Response:
    """Prometheus scrape endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
