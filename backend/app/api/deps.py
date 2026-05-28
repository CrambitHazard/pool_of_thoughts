"""FastAPI dependency helpers."""

from functools import lru_cache

from app.cognitive.thought_extraction import ThoughtExtractionService
from app.config.settings import Settings, get_settings
from app.services.llm.factory import create_llm_provider


@lru_cache
def get_thought_extraction_service() -> ThoughtExtractionService:
    """Return a cached thought extraction service.

    Returns:
        ThoughtExtractionService: Configured extraction service.
    """
    settings = get_settings()
    provider = create_llm_provider(settings)
    return ThoughtExtractionService(provider, settings)


def get_app_settings() -> Settings:
    """Return application settings for route handlers.

    Returns:
        Settings: Loaded configuration values.
    """
    return get_settings()
