"""Core API routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from app.api.deps import (
    get_app_settings,
    get_cognition_runtime,
    get_consolidation_service,
    get_session_maker,
    get_thought_extraction_service,
)
from app.api.schemas import (
    ActivityEventRead,
    CognitionStateResponse,
    ThoughtExtractionResponse,
    UserMessageInput,
)
from app.cognitive.thought_extraction import ThoughtExtractionError, ThoughtExtractionService
from app.config.settings import Settings
from app.memory.abstraction_repository import MemoryAbstractionRepository
from app.memory.consolidation import ConsolidationService
from app.models.schemas import MemoryAbstractionRead, ThoughtCreate
from app.services.cognition_runtime import CognitionRuntime
from app.services.database import init_db
from app.services.llm.base import LLMProviderError

router = APIRouter()


def _build_state_response(
    runtime: CognitionRuntime,
    abstractions: list[MemoryAbstractionRead] | None = None,
) -> CognitionStateResponse:
    """Convert runtime state into an API response.

    Args:
        runtime: Live cognition runtime.
        abstractions: Optional long-term memory records.

    Returns:
        CognitionStateResponse: Serializable cognition state.
    """
    state = runtime.get_state()
    return CognitionStateResponse(
        working_memory=state.working_memory,
        backlog=state.backlog,
        activity=[ActivityEventRead.model_validate(event.__dict__) for event in state.activity],
        abstractions=abstractions or [],
        working_capacity=state.working_capacity,
        tick_count=state.tick_count,
    )


def _load_abstractions() -> list[MemoryAbstractionRead]:
    """Load stored semantic abstractions from SQLite.

    Returns:
        list[MemoryAbstractionRead]: Long-term memory records.
    """
    init_db()
    session = get_session_maker()()
    try:
        repository = MemoryAbstractionRepository(session)
        return repository.list_all()
    finally:
        session.close()


@router.get("/health")
def health_check() -> dict[str, str]:
    """Return service health status.

    Returns:
        dict[str, str]: Health payload with status and service name.
    """
    return {"status": "ok", "service": "laguna-backend"}


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


@router.get("/cognition/state", response_model=CognitionStateResponse)
def cognition_state(
    runtime: CognitionRuntime = Depends(get_cognition_runtime),
) -> CognitionStateResponse:
    """Return the current cognitive workspace state."""
    return _build_state_response(runtime, _load_abstractions())


@router.post("/cognition/ingest", response_model=CognitionStateResponse)
async def cognition_ingest(
    payload: UserMessageInput,
    runtime: CognitionRuntime = Depends(get_cognition_runtime),
) -> CognitionStateResponse:
    """Extract and ingest thoughts from a raw message."""
    try:
        await runtime.ingest_message(payload.message)
    except ThoughtExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return _build_state_response(runtime, _load_abstractions())


@router.post("/cognition/tick", response_model=CognitionStateResponse)
def cognition_tick(
    runtime: CognitionRuntime = Depends(get_cognition_runtime),
) -> CognitionStateResponse:
    """Run one cognitive loop tick."""
    runtime.run_tick()
    return _build_state_response(runtime, _load_abstractions())


@router.post("/cognition/demo", response_model=CognitionStateResponse)
def seed_demo_thoughts(
    runtime: CognitionRuntime = Depends(get_cognition_runtime),
) -> CognitionStateResponse:
    """Seed demo thoughts for UI development without LLM calls."""
    demo_thoughts = [
        ThoughtCreate(
            content="Finish Laguna memory model draft",
            source="user_input",
            salience=0.82,
            novelty=0.2,
        ),
        ThoughtCreate(
            content="Explore systems programming with Rust",
            source="user_input",
            salience=0.74,
            novelty=0.55,
        ),
        ThoughtCreate(
            content="Review backlog resurfacing heuristics",
            source="inferred",
            salience=0.48,
            novelty=0.35,
        ),
        ThoughtCreate(
            content="Schedule reflection consolidation cycle",
            source="inferred",
            salience=0.41,
            novelty=0.25,
        ),
    ]

    for payload in demo_thoughts:
        runtime.ingest_thought(payload)

    return _build_state_response(runtime, _load_abstractions())


@router.post("/reflection/run", response_model=CognitionStateResponse)
async def run_reflection(
    service: ConsolidationService = Depends(get_consolidation_service),
    runtime: CognitionRuntime = Depends(get_cognition_runtime),
) -> CognitionStateResponse:
    """Run one reflection and consolidation cycle."""
    try:
        result = await service.consolidate()
    except (LLMProviderError, ValidationError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    runtime.log_reflection(result.created, result.updated)
    return _build_state_response(runtime, _load_abstractions())


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
