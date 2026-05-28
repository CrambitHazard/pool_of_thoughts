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
from app.cognitive.prompt_context import LAGUNA_SYSTEM_NAME
from app.cognitive.prompts import EXTRACTION_SYSTEM_PROMPT, build_extraction_prompt
from app.cognitive.reflection import ReflectionEngine, ReflectionResult
from app.cognitive.reflection_prompts import REFLECTION_SYSTEM_PROMPT, build_abstraction_prompt
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
    "EXTRACTION_SYSTEM_PROMPT",
    "INTERRUPTION_MARGIN",
    "INTERRUPTION_SALIENCE_THRESHOLD",
    "LAGUNA_SYSTEM_NAME",
    "MERGE_SIMILARITY_THRESHOLD",
    "NOVELTY_THRESHOLD",
    "REPEATED_RELEVANCE_MIN_RESURFACES",
    "REPEATED_RELEVANCE_MIN_SALIENCE",
    "REFLECTION_SYSTEM_PROMPT",
    "ReflectionEngine",
    "ReflectionResult",
    "ResurfacingStrategy",
    "ThoughtConflictResolver",
    "ThoughtExtractionError",
    "ThoughtExtractionResult",
    "ThoughtExtractionService",
    "ThoughtSimilarity",
    "build_abstraction_prompt",
    "build_extraction_prompt",
]
