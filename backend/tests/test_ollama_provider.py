"""Ollama provider tests."""

import asyncio
import json

import httpx
import pytest

from app.config.settings import Settings
from app.services.llm.base import LLMProviderError
from app.services.llm.factory import create_llm_provider
from app.services.llm.ollama import OllamaProvider


def test_create_llm_provider_returns_ollama_by_default() -> None:
    """Factory creates an Ollama provider from settings."""
    provider = create_llm_provider(Settings())
    assert isinstance(provider, OllamaProvider)


def test_ollama_provider_sends_deterministic_request() -> None:
    """Ollama provider posts a JSON chat request with configured model options."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["payload"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={"message": {"content": json.dumps({"ok": True})}},
        )

    settings = Settings(
        ollama_model="gemma:2b",
        ollama_temperature=0.0,
        ollama_seed=42,
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(settings, client=client)

    result = asyncio.run(
        provider.complete_json("system", "user"),
    )

    assert result == json.dumps({"ok": True})
    assert captured["url"].endswith("/api/chat")
    assert captured["payload"]["model"] == "gemma:2b"
    assert captured["payload"]["format"] == "json"
    assert captured["payload"]["options"]["temperature"] == 0.0
    assert captured["payload"]["options"]["seed"] == 42


def test_ollama_provider_raises_on_http_error() -> None:
    """HTTP failures are wrapped as LLMProviderError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "model unavailable"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(Settings(), client=client)

    with pytest.raises(LLMProviderError):
        asyncio.run(provider.complete_json("system", "user"))
