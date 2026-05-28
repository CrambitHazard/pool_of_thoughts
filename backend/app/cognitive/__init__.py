"""Cognitive processing modules (attention, reasoning, orchestration)."""

from app.cognitive.loop import CognitiveLoop, CognitiveLoopTickResult
from app.cognitive.resurfacing import (
    NOVELTY_THRESHOLD,
    REPEATED_RELEVANCE_MIN_RESURFACES,
    REPEATED_RELEVANCE_MIN_SALIENCE,
    ResurfacingStrategy,
)
from app.cognitive.thought_extraction import (
    ExtractedThought,
    ThoughtExtractionError,
    ThoughtExtractionResult,
    ThoughtExtractionService,
)

__all__ = [
    "CognitiveLoop",
    "CognitiveLoopTickResult",
    "ExtractedThought",
    "NOVELTY_THRESHOLD",
    "REPEATED_RELEVANCE_MIN_RESURFACES",
    "REPEATED_RELEVANCE_MIN_SALIENCE",
    "ResurfacingStrategy",
    "ThoughtExtractionError",
    "ThoughtExtractionResult",
    "ThoughtExtractionService",
]
