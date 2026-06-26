from __future__ import annotations

import time

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

REQUEST_COUNTER = Counter(
    "llm_requests_total",
    "Total number of LLM inference requests",
    ["model", "status_code"],
)

REQUEST_DURATION = Histogram(
    "llm_request_duration_seconds",
    "LLM inference request duration in seconds",
    ["model"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

TOKENS_COUNTER = Counter(
    "llm_tokens_used_total",
    "Total tokens consumed",
    ["model", "type"],  # type: prompt | completion
)


def record_token_usage(model: str, prompt_tokens: int, completion_tokens: int) -> None:
    """Record token usage after a successful inference call."""
    TOKENS_COUNTER.labels(model=model, type="prompt").inc(prompt_tokens)
    TOKENS_COUNTER.labels(model=model, type="completion").inc(completion_tokens)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Track request count and latency for every HTTP request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        # Only track inference endpoint in the duration/counter metrics.
        # Health and metrics endpoints are intentionally excluded to keep
        # dashboards clean, but the middleware runs on all paths.
        model = request.headers.get("x-model-label", "unknown")

        REQUEST_COUNTER.labels(
            model=model,
            status_code=str(response.status_code),
        ).inc()

        REQUEST_DURATION.labels(model=model).observe(duration)

        return response
