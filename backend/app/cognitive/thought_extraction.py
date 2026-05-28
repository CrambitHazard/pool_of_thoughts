"""Extract structured thoughts from raw user input."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, ValidationError

from app.cognitive.prompts import EXTRACTION_SYSTEM_PROMPT, build_extraction_prompt
from app.config.settings import Settings, get_settings
from app.models.schemas import ThoughtCreate
from app.services.llm.base import LLMProvider, LLMProviderError


class ThoughtExtractionError(Exception):
    """Raised when thought extraction or parsing fails."""


class ExtractedThought(BaseModel):
    """Structured thought fields produced by the cognition engine."""

    content: str = Field(min_length=1, max_length=280)
    salience: float = Field(default=0.5, ge=0.0, le=1.0)
    emotional_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    novelty: float = Field(default=0.0, ge=0.0, le=1.0)


class ThoughtExtractionResult(BaseModel):
    """Structured output from parsing a user message."""

    input_message: str
    summary: str
    primary_thought: ExtractedThought
    related_thoughts: list[ExtractedThought] = Field(default_factory=list)

    def to_thought_creates(self) -> list[ThoughtCreate]:
        """Convert extraction output into thought creation payloads.

        Returns:
            list[ThoughtCreate]: Primary and related thought objects.
        """
        primary = ThoughtCreate(
            content=self.primary_thought.content,
            source="user_input",
            salience=self.primary_thought.salience,
            emotional_weight=self.primary_thought.emotional_weight,
            novelty=self.primary_thought.novelty,
            metadata_json={
                "summary": self.summary,
                "role": "primary",
                "input_message": self.input_message,
            },
        )
        related = [
            ThoughtCreate(
                content=thought.content,
                source="inferred",
                salience=thought.salience,
                emotional_weight=thought.emotional_weight,
                novelty=thought.novelty,
                metadata_json={
                    "summary": self.summary,
                    "role": "related",
                    "input_message": self.input_message,
                },
            )
            for thought in self.related_thoughts
        ]
        return [primary, *related]


class ThoughtExtractionService:
    """Use an LLM provider to extract structured thoughts from input."""

    def __init__(
        self,
        provider: LLMProvider,
        settings: Settings | None = None,
    ) -> None:
        """Initialize the extraction service.

        Args:
            provider: LLM provider used for cognition parsing.
            settings: Optional settings override.
        """
        self.provider = provider
        self.settings = settings or get_settings()

    async def extract_from_message(self, message: str) -> ThoughtExtractionResult:
        """Extract structured thoughts from a raw user message.

        Args:
            message: Raw user input text.

        Returns:
            ThoughtExtractionResult: Parsed primary, summary, and related thoughts.

        Raises:
            ThoughtExtractionError: When input is empty or parsing fails.
            LLMProviderError: When the provider call fails.
        """
        cleaned = message.strip()
        if not cleaned:
            raise ThoughtExtractionError("Input message must not be empty.")

        prompt = build_extraction_prompt(
            cleaned,
            max_related=self.settings.ollama_max_related_thoughts,
        )

        try:
            raw_json = await self.provider.complete_json(
                EXTRACTION_SYSTEM_PROMPT,
                prompt,
            )
            payload = _parse_json_response(raw_json)
            result = ThoughtExtractionResult(
                input_message=cleaned,
                summary=payload["summary"],
                primary_thought=ExtractedThought.model_validate(payload["primary_thought"]),
                related_thoughts=[
                    ExtractedThought.model_validate(item)
                    for item in payload.get("related_thoughts", [])
                ],
            )
            return result
        except (ValidationError, KeyError, json.JSONDecodeError, TypeError) as exc:
            raise ThoughtExtractionError(f"Invalid extraction payload: {exc}") from exc


def _parse_json_response(raw: str) -> dict:
    """Parse JSON from a model response, stripping optional code fences.

    Args:
        raw: Raw model output.

    Returns:
        dict: Parsed JSON object.

    Raises:
        json.JSONDecodeError: When the payload is not valid JSON.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise TypeError("Extraction payload must be a JSON object.")
    return data
