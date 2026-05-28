"""Contextual salience adaptation package."""

from app.cognitive.context.activity_log import ActivityLog, DEFAULT_ACTIVITY_TAG_LEXICON
from app.cognitive.context.engine import (
    DEFAULT_TRIGGER_RULES,
    ContextEngine,
    ContextEngineConfig,
)
from app.cognitive.context.types import (
    ActivityRecord,
    ContextRecalcResult,
    ContextState,
    ContextWindow,
    SalienceAdjustment,
    TriggerRule,
)

__all__ = [
    "ActivityLog",
    "ActivityRecord",
    "ContextEngine",
    "ContextEngineConfig",
    "ContextRecalcResult",
    "ContextState",
    "ContextWindow",
    "DEFAULT_ACTIVITY_TAG_LEXICON",
    "DEFAULT_TRIGGER_RULES",
    "SalienceAdjustment",
    "TriggerRule",
]
