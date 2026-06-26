from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from app.middleware.metrics import record_token_usage
from app.models.schemas import ChatRequest, ChatResponse
from app.services.gemini import GeminiError, call_gemini

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/chat", response_model=ChatResponse, summary="Chat completion")
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """
    OpenAI-compatible chat completion endpoint backed by Google Gemini.

    Accepts a list of messages and returns a completion from the configured model.
    """
    try:
        result = await call_gemini(body)
    except GeminiError as exc:
        logger.error("Gemini call failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Record token usage metrics
    record_token_usage(
        model=result.model,
        prompt_tokens=result.usage.prompt_tokens,
        completion_tokens=result.usage.completion_tokens,
    )

    # Attach model label to request so middleware can tag the duration metric
    request.state.model = result.model

    return result
