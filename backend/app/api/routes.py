"""Core API routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from app.api.deps import (
    get_app_settings,
    get_consolidation_service,
    get_session_maker,
    get_thought_extraction_service,
)
from app.api.schemas import ThoughtExtractionResponse, UserMessageInput
from app.cognitive.reflection import ReflectionEngine
from app.cognitive.thought_extraction import ThoughtExtractionError, ThoughtExtractionService
from app.config.settings import Settings
from app.memory.abstraction_repository import MemoryAbstractionRepository
from app.memory.consolidation import ConsolidationService
from app.models.schemas import MemoryAbstractionRead
from app.services.database import init_db
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
        "reflection_interval_minutes": settings.reflection_interval_minutes,
        "reflection_lookback_hours": settings.reflection_lookback_hours,
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


@router.post("/reflection/run")
async def run_reflection(
    service: ConsolidationService = Depends(get_consolidation_service),
) -> dict[str, object]:
    """Run one reflection and consolidation cycle.

    Args:
        service: Consolidation service dependency.

    Returns:
        dict[str, object]: Consolidation summary.

    Raises:
        HTTPException: When abstraction generation fails.
    """
    try:
        result = await service.consolidate()
    except (LLMProviderError, ValidationError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "reviewed_thoughts": result.reviewed_thoughts,
        "theme_clusters": result.theme_clusters,
        "created": result.created,
        "updated": result.updated,
        "consolidated_thought_ids": result.consolidated_thought_ids,
    }


@router.get("/reflection/abstractions", response_model=list[MemoryAbstractionRead])
def list_abstractions() -> list[MemoryAbstractionRead]:
    """List stored semantic memory abstractions.

    Returns:
        list[MemoryAbstractionRead]: Consolidated long-term memories.
    """
    init_db()
    session = get_session_maker()()
    try:
        repository = MemoryAbstractionRepository(session)
        return repository.list_all()
    finally:
        session.close()
