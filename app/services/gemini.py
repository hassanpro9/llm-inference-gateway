from __future__ import annotations

import os
import logging

import httpx

from app.models.schemas import ChatRequest, ChatResponse, Choice, MessageResponse, Usage

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiError(Exception):
    """Raised when the Gemini API returns an error."""


def _build_gemini_contents(request: ChatRequest) -> list[dict]:
    """Convert OpenAI-style messages to Gemini contents format."""
    contents = []
    for msg in request.messages:
        role = "model" if msg.role == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg.content}]})
    return contents


async def call_gemini(request: ChatRequest) -> ChatResponse:
    """Send a chat request to the Gemini API and return an OpenAI-compatible response."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise GeminiError("GEMINI_API_KEY environment variable is not set")

    model = request.model
    url = f"{GEMINI_API_BASE}/{model}:generateContent"

    payload = {
        "contents": _build_gemini_contents(request),
        "generationConfig": {
            "maxOutputTokens": request.max_tokens,
        },
    }

    logger.debug("Sending request to Gemini model=%s", model)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url,
            json=payload,
            params={"key": api_key},
        )

    if resp.status_code != 200:
        logger.error("Gemini API error status=%d body=%s", resp.status_code, resp.text)
        raise GeminiError(f"Gemini API returned {resp.status_code}: {resp.text}")

    data = resp.json()

    try:
        candidate = data["candidates"][0]
        content_text = candidate["content"]["parts"][0]["text"]
        finish_reason = candidate.get("finishReason", "STOP").lower()

        usage_meta = data.get("usageMetadata", {})
        prompt_tokens = usage_meta.get("promptTokenCount", 0)
        completion_tokens = usage_meta.get("candidatesTokenCount", 0)

        return ChatResponse(
            model=model,
            choices=[
                Choice(
                    message=MessageResponse(content=content_text),
                    finish_reason=finish_reason,
                )
            ],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )
    except (KeyError, IndexError) as exc:
        logger.error("Unexpected Gemini response structure: %s", data)
        raise GeminiError(f"Unexpected response structure from Gemini: {exc}") from exc
