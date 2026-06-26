from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models.schemas import ChatResponse, Choice, MessageResponse, Usage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MOCK_RESPONSE = ChatResponse(
    model="gemini-2.5-flash",
    choices=[
        Choice(
            message=MessageResponse(content="Kubernetes orchestrates containers."),
            finish_reason="stop",
        )
    ],
    usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
)

VALID_PAYLOAD = {
    "model": "gemini-2.5-flash",
    "messages": [{"role": "user", "content": "What is Kubernetes?"}],
    "max_tokens": 256,
}


# ---------------------------------------------------------------------------
# /v1/chat
# ---------------------------------------------------------------------------


def test_chat_success(client: TestClient) -> None:
    with patch(
        "app.routers.inference.call_gemini",
        new_callable=AsyncMock,
        return_value=MOCK_RESPONSE,
    ):
        resp = client.post("/v1/chat", json=VALID_PAYLOAD)

    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "gemini-2.5-flash"
    assert len(data["choices"]) == 1
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert "content" in data["choices"][0]["message"]
    assert data["usage"]["total_tokens"] == 15


def test_chat_missing_messages(client: TestClient) -> None:
    resp = client.post("/v1/chat", json={"model": "gemini-2.5-flash"})
    assert resp.status_code == 422


def test_chat_empty_messages(client: TestClient) -> None:
    resp = client.post("/v1/chat", json={"messages": []})
    assert resp.status_code == 422


def test_chat_gemini_error_returns_502(client: TestClient) -> None:
    from app.services.gemini import GeminiError

    with patch(
        "app.routers.inference.call_gemini",
        new_callable=AsyncMock,
        side_effect=GeminiError("upstream failure"),
    ):
        resp = client.post("/v1/chat", json=VALID_PAYLOAD)

    assert resp.status_code == 502
    assert "upstream failure" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# /ready
# ---------------------------------------------------------------------------


def test_ready_with_key(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["gemini_key_configured"] is True


def test_ready_without_key(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    resp = client.get("/ready")
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# /metrics
# ---------------------------------------------------------------------------


def test_metrics_endpoint(client: TestClient) -> None:
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "llm_requests_total" in resp.text
