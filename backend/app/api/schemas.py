"""API request and response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.cognitive.thought_extraction import ThoughtExtractionResult
from app.models.schemas import MemoryAbstractionRead, ThoughtRead

ActivityType = Literal[
    "thought_added",
    "thought_merged",
    "thought_interrupted",
    "thought_replaced",
    "thought_evicted",
    "thought_resurfaced",
    "tick_complete",
    "reflection_complete",
    "input_received",
    "graph_activated",
    "context_recalculated",
]


class UserMessageInput(BaseModel):
    """Raw user message submitted for cognition parsing."""

    message: str = Field(min_length=1, max_length=4000)


class ThoughtExtractionResponse(ThoughtExtractionResult):
    """Structured thought extraction returned to clients."""

    pass


class ActivityEventRead(BaseModel):
    """Activity feed event returned to clients."""

    id: str
    type: ActivityType
    message: str
    timestamp: datetime
    thought_id: str | None = None
    source_panel: str | None = None
    target_panel: str | None = None


class CognitionStateResponse(BaseModel):
    """Current cognitive workspace state."""

    working_memory: list[ThoughtRead]
    backlog: list[ThoughtRead]
    activity: list[ActivityEventRead]
    abstractions: list[MemoryAbstractionRead] = Field(default_factory=list)
    working_capacity: int
    tick_count: int


class ContextSnapshotResponse(BaseModel):
    """Active contextual signals across temporal windows."""

    immediate: dict[str, float]
    daily: dict[str, float]
    long_term: dict[str, float]
    activity_count: int
