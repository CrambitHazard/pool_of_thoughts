"""Factory helpers for contextual salience engines."""

from app.cognitive.context import ContextEngine, ContextEngineConfig
from app.config.settings import Settings


def build_context_engine(settings: Settings | None = None) -> ContextEngine:
    """Build a configured context engine from application settings.

    Args:
        settings: Optional settings override.

    Returns:
        ContextEngine: Configured contextual salience engine.
    """
    from app.config.settings import get_settings

    active_settings = settings or get_settings()
    config = ContextEngineConfig(
        immediate_minutes=active_settings.context_immediate_minutes,
        daily_hours=active_settings.context_daily_hours,
        long_term_days=active_settings.context_long_term_days,
        max_adjustment=active_settings.context_max_adjustment,
        recurring_min_occurrences=active_settings.context_recurring_min_occurrences,
    )
    return ContextEngine(config=config)
