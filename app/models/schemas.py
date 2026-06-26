from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    model: str = "gemini-1.5-flash"
    messages: list[Message] = Field(..., min_length=1)
    max_tokens: int = Field(default=1024, ge=1, le=8192)


class MessageResponse(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class Choice(BaseModel):
    message: MessageResponse
    finish_reason: str = "stop"
    index: int = 0


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    object: str = "chat.completion"
    model: str
    choices: list[Choice]
    usage: Usage


class HealthResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    gemini_key_configured: bool
