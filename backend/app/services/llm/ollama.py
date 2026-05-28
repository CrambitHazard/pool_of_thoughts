"""Ollama LLM provider."""

from __future__ import annotations

import httpx

from app.config.settings import Settings
from app.services.llm.base import LLMProvider, LLMProviderError


class OllamaProvider(LLMProvider):
    """Local model provider backed by Ollama."""

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize the Ollama provider.

        Args:
            settings: Application settings with Ollama configuration.
            client: Optional HTTP client for tests.
        """
        self.settings = settings
        self._client = client
        self._owns_client = client is None

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Request a JSON completion from Ollama.

        Args:
            system_prompt: System instructions for the model.
            user_prompt: User-side task prompt.

        Returns:
            str: Raw JSON text from Ollama.

        Raises:
            LLMProviderError: When Ollama returns an error response.
        """
        payload = {
            "model": self.settings.ollama_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.settings.ollama_temperature,
                "seed": self.settings.ollama_seed,
            },
        }
        url = f"{self.settings.ollama_base_url.rstrip('/')}/api/chat"

        client = self._client or httpx.AsyncClient(
            timeout=self.settings.ollama_timeout_seconds,
        )
        close_client = self._owns_client and self._client is None

        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            message = data.get("message", {})
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                raise LLMProviderError("Ollama returned an empty completion.")
            return content.strip()
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"Ollama request failed: {exc}") from exc
        finally:
            if close_client:
                await client.aclose()
