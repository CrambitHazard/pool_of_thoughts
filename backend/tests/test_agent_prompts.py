"""Prompt contract tests for Laguna agents."""

import asyncio

from app.cognitive.prompt_context import LAGUNA_SYSTEM_NAME
from app.cognitive.prompts import EXTRACTION_SYSTEM_PROMPT, build_extraction_prompt
from app.cognitive.reflection_prompts import REFLECTION_SYSTEM_PROMPT, build_abstraction_prompt
from app.cognitive.thought_extraction import ThoughtExtractionService
from app.config.settings import Settings
from tests.test_thought_extraction import FakeLLMProvider


def test_extraction_system_prompt_uses_laguna_identity() -> None:
    """Extraction agent prompt identifies Laguna and forbids chat behavior."""
    assert LAGUNA_SYSTEM_NAME in EXTRACTION_SYSTEM_PROMPT
    assert "not a user-facing assistant" in EXTRACTION_SYSTEM_PROMPT
    assert "valid JSON object only" in EXTRACTION_SYSTEM_PROMPT


def test_reflection_system_prompt_uses_laguna_identity() -> None:
    """Reflection agent prompt identifies Laguna and enforces generalization."""
    assert LAGUNA_SYSTEM_NAME in REFLECTION_SYSTEM_PROMPT
    assert "semantic memory" in REFLECTION_SYSTEM_PROMPT
    assert "Never quote source thoughts verbatim" in REFLECTION_SYSTEM_PROMPT


def test_extraction_user_prompt_is_deterministic_and_structured() -> None:
    """User prompt template remains stable for identical input."""
    first = build_extraction_prompt("same input", max_related=2)
    second = build_extraction_prompt("same input", max_related=2)

    assert first == second
    assert "related_thoughts" in first
    assert "primary_thought" in first


def test_reflection_user_prompt_includes_theme_hint_and_sources() -> None:
    """Abstraction prompt carries cluster context and consolidation rules."""
    prompt = build_abstraction_prompt(
        ["I want to learn Rust", "I watched systems programming videos"],
        "systems programming rust",
    )

    assert "systems programming rust" in prompt
    assert "I want to learn Rust" in prompt
    assert "Target outcome example" in prompt


def test_extraction_service_uses_refined_system_prompt() -> None:
    """Thought extraction forwards the Laguna extraction system prompt."""
    provider = FakeLLMProvider()
    service = ThoughtExtractionService(provider, settings=Settings(ollama_max_related_thoughts=2))

    asyncio.run(service.extract_from_message("finish memory model draft"))

    assert provider.last_system_prompt == EXTRACTION_SYSTEM_PROMPT
    assert "Task: extract structured thoughts" in (provider.last_user_prompt or "")
