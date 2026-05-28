"""LLM provider abstraction."""

from abc import ABC, abstractmethod


class LLMProviderError(Exception):
    """Raised when an LLM provider request fails."""


class LLMProvider(ABC):
    """Abstract interface for text completion providers."""

    @abstractmethod
    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Return a JSON string completion from the model.

        Args:
            system_prompt: System instructions for the model.
            user_prompt: User-side task prompt.

        Returns:
            str: Raw JSON text from the provider.

        Raises:
            LLMProviderError: When the provider call fails.
        """
