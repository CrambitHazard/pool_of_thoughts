"""Environment-backed application settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """AttentionOS runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ATTENTIONOS_",
        extra="ignore",
    )

    llm_provider: Literal["ollama"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma:2b"
    ollama_temperature: float = 0.0
    ollama_seed: int = 42
    ollama_timeout_seconds: float = 120.0
    ollama_max_related_thoughts: int = 3


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings.

    Returns:
        Settings: Loaded configuration values.
    """
    return Settings()
