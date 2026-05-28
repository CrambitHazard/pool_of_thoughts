"""Thought extraction service tests."""

import asyncio
import json

import pytest

from app.cognitive.thought_extraction import (
    ThoughtExtractionError,
    ThoughtExtractionService,
)
from app.config.settings import Settings


SAMPLE_RESPONSE = {
    "primary_thought": {
        "content": "Need to finish memory model draft",
        "salience": 0.82,
        "emotional_weight": 0.15,
        "novelty": 0.2,
    },
    "summary": "Finish the memory model draft soon",
    "related_thoughts": [
        {
            "content": "Review backlog resurfacing rules",
            "salience": 0.45,
            "emotional_weight": 0.0,
            "novelty": 0.55,
        }
    ],
}


class FakeLLMProvider:
    """Deterministic LLM stub for extraction tests."""

    def __init__(self, payload: dict | None = None, fail: bool = False) -> None:
        self.payload = payload or SAMPLE_RESPONSE
        self.fail = fail
        self.last_system_prompt: str | None = None
        self.last_user_prompt: str | None = None

    async def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        """Return a fixed JSON payload.

        Args:
            system_prompt: Captured system prompt.
            user_prompt: Captured user prompt.

        Returns:
            str: JSON string completion.
        """
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        if self.fail:
            raise RuntimeError("provider failure")
        return json.dumps(self.payload)


def test_extract_from_message_returns_structured_thoughts() -> None:
    """Extraction parses primary, summary, and related thoughts."""
    service = ThoughtExtractionService(
        FakeLLMProvider(),
        settings=Settings(ollama_max_related_thoughts=3),
    )

    result = asyncio.run(service.extract_from_message("  finish memory model draft  "))

    assert result.input_message == "finish memory model draft"
    assert result.summary == "Finish the memory model draft soon"
    assert result.primary_thought.content == "Need to finish memory model draft"
    assert len(result.related_thoughts) == 1


def test_extract_to_thought_creates_maps_sources() -> None:
    """Structured extraction converts into ThoughtCreate payloads."""
    service = ThoughtExtractionService(FakeLLMProvider())
    result = asyncio.run(service.extract_from_message("finish memory model draft"))

    thoughts = result.to_thought_creates()

    assert thoughts[0].source == "user_input"
    assert thoughts[1].source == "inferred"
    assert thoughts[0].metadata_json["summary"] == result.summary


def test_extract_rejects_empty_message() -> None:
    """Empty input raises a ThoughtExtractionError."""
    service = ThoughtExtractionService(FakeLLMProvider())

    with pytest.raises(ThoughtExtractionError):
        asyncio.run(service.extract_from_message("   "))


def test_extract_rejects_invalid_json_payload() -> None:
    """Invalid model JSON raises a ThoughtExtractionError."""

    class BadJSONProvider:
        async def complete_json(self, system_prompt: str, user_prompt: str) -> str:
            return "not-json"

    service = ThoughtExtractionService(BadJSONProvider())

    with pytest.raises(ThoughtExtractionError):
        asyncio.run(service.extract_from_message("hello"))


def test_prompt_is_deterministic_for_same_input() -> None:
    """Repeated extraction uses the same prompt template."""
    provider = FakeLLMProvider()
    service = ThoughtExtractionService(provider, settings=Settings(ollama_max_related_thoughts=2))

    asyncio.run(service.extract_from_message("same input"))
    first_prompt = provider.last_user_prompt
    asyncio.run(service.extract_from_message("same input"))
    second_prompt = provider.last_user_prompt

    assert first_prompt == second_prompt
    assert "same input" in first_prompt
