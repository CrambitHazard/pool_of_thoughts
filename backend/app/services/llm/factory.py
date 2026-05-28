"""LLM provider factory."""

from app.config.settings import Settings, get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.ollama import OllamaProvider


def create_llm_provider(settings: Settings | None = None) -> LLMProvider:
    """Create an LLM provider from application settings.

    Args:
        settings: Optional settings override.

    Returns:
        LLMProvider: Configured provider instance.

    Raises:
        ValueError: When the configured provider is unsupported.
    """
    config = settings or get_settings()

    if config.llm_provider == "ollama":
        return OllamaProvider(config)

    raise ValueError(f"Unsupported LLM provider: {config.llm_provider}")
