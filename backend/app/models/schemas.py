"""Pydantic schemas for thought objects."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ThoughtCreate(BaseModel):
    """Payload for creating a new thought."""

    content: str
    source: str
    salience: float = 0.5
    emotional_weight: float = 0.0
    novelty: float = 0.0
    resolved: bool = False
    expires_at: datetime | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ThoughtUpdateSalience(BaseModel):
    """Payload for updating thought salience."""

    salience: float


class ThoughtRead(BaseModel):
    """Thought object returned from the cognitive layer."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    content: str
    source: str
    salience: float
    emotional_weight: float
    novelty: float
    resolved: bool
    created_at: datetime
    expires_at: datetime | None
    times_resurfaced: int
    last_accessed: datetime
    metadata_json: dict[str, Any]
