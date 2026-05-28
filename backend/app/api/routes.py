"""Core API routes."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_app_settings, get_thought_extraction_service
from app.api.schemas import ThoughtExtractionResponse, UserMessageInput
from app.cognitive.thought_extraction import ThoughtExtractionError, ThoughtExtractionService
from app.config.settings import Settings
from app.services.llm.base import LLMProviderError

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    """Return service health status.

    Returns:
        dict[str, str]: Health payload with status and service name.
    """
    return {"status": "ok", "service": "attentionos-backend"}


@router.get("/cognition/config")
def cognition_config(settings: Settings = Depends(get_app_settings)) -> dict[str, str | float | int]:
    """Return active cognition and LLM configuration.

    Args:
        settings: Application settings dependency.

    Returns:
        dict[str, str | float | int]: Non-secret runtime configuration.
    """
    return {
        "llm_provider": settings.llm_provider,
        "ollama_model": settings.ollama_model,
        "ollama_base_url": settings.ollama_base_url,
        "ollama_temperature": settings.ollama_temperature,
        "ollama_max_related_thoughts": settings.ollama_max_related_thoughts,
    }


@router.post("/cognition/extract", response_model=ThoughtExtractionResponse)
async def extract_thoughts(
    payload: UserMessageInput,
    service: ThoughtExtractionService = Depends(get_thought_extraction_service),
) -> ThoughtExtractionResponse:
    """Extract structured thoughts from a raw user message.

    Args:
        payload: Raw user message input.
        service: Thought extraction service dependency.

    Returns:
        ThoughtExtractionResponse: Structured cognition output.

    Raises:
        HTTPException: When extraction or provider calls fail.
    """
    try:
        result = await service.extract_from_message(payload.message)
        return ThoughtExtractionResponse.model_validate(result.model_dump())
    except ThoughtExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
