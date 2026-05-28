"""Cognitive processing modules (attention, reasoning, orchestration)."""

from app.cognitive.loop import CognitiveLoop, CognitiveLoopTickResult
from app.cognitive.resurfacing import (
    NOVELTY_THRESHOLD,
    REPEATED_RELEVANCE_MIN_RESURFACES,
    REPEATED_RELEVANCE_MIN_SALIENCE,
    ResurfacingStrategy,
)

__all__ = [
    "CognitiveLoop",
    "CognitiveLoopTickResult",
    "NOVELTY_THRESHOLD",
    "REPEATED_RELEVANCE_MIN_RESURFACES",
    "REPEATED_RELEVANCE_MIN_SALIENCE",
    "ResurfacingStrategy",
]
