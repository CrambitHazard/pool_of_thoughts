"""Cognitive processing modules (attention, reasoning, orchestration)."""

from app.cognitive.arbitrator import (
    INTERRUPTION_MARGIN,
    INTERRUPTION_SALIENCE_THRESHOLD,
    AttentionArbitrator,
    AttentionResult,
)
from app.cognitive.conflict import (
    CONFLICT_MIN_SIMILARITY,
    CONFLICT_SALIENCE_PENALTY,
    ThoughtConflictResolver,
)
from app.cognitive.loop import CognitiveLoop, CognitiveLoopTickResult
from app.cognitive.resurfacing import (
    NOVELTY_THRESHOLD,
    REPEATED_RELEVANCE_MIN_RESURFACES,
    REPEATED_RELEVANCE_MIN_SALIENCE,
    ResurfacingStrategy,
)
from app.cognitive.similarity import MERGE_SIMILARITY_THRESHOLD, ThoughtSimilarity
from app.cognitive.thought_extraction import (
    ExtractedThought,
    ThoughtExtractionError,
    ThoughtExtractionResult,
    ThoughtExtractionService,
)

__all__ = [
    "AttentionArbitrator",
    "AttentionResult",
    "CognitiveLoop",
    "CognitiveLoopTickResult",
    "CONFLICT_MIN_SIMILARITY",
    "CONFLICT_SALIENCE_PENALTY",
    "ExtractedThought",
    "INTERRUPTION_MARGIN",
    "INTERRUPTION_SALIENCE_THRESHOLD",
    "MERGE_SIMILARITY_THRESHOLD",
    "NOVELTY_THRESHOLD",
    "REPEATED_RELEVANCE_MIN_RESURFACES",
    "REPEATED_RELEVANCE_MIN_SALIENCE",
    "ResurfacingStrategy",
    "ThoughtConflictResolver",
    "ThoughtExtractionError",
    "ThoughtExtractionResult",
    "ThoughtExtractionService",
    "ThoughtSimilarity",
]
