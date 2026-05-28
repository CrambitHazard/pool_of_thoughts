"""Pydantic schemas for thought objects."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.graph_types import RelationType


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


class MemoryAbstractionCreate(BaseModel):
    """Payload for storing a consolidated semantic memory."""

    summary: str = Field(min_length=1, max_length=500)
    theme: str = Field(min_length=1, max_length=255)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    support_count: int = Field(default=1, ge=1)
    source_thought_ids: list[str] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class MemoryAbstractionRead(BaseModel):
    """Compressed semantic memory returned from consolidation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    summary: str
    theme: str
    confidence: float
    support_count: int
    source_thought_ids: list[str]
    created_at: datetime
    updated_at: datetime
    metadata_json: dict[str, Any]


class ThoughtLinkCreate(BaseModel):
    """Payload for creating a weighted thought association."""

    source_thought_id: str
    target_thought_id: str
    relation: RelationType
    weight: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ThoughtLinkRead(BaseModel):
    """Persisted edge in the associative thought graph."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    source_thought_id: str
    target_thought_id: str
    relation_type: str
    weight: float
    created_at: datetime
    updated_at: datetime
    metadata_json: dict[str, Any]

    @property
    def relation(self) -> RelationType:
        """Return the typed relation enum.

        Returns:
            RelationType: Parsed relation type.
        """
        return RelationType(self.relation_type)


class ThoughtClusterRead(BaseModel):
    """Persisted recurring theme cluster."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    thought_ids: list[str]
    cohesion: float
    created_at: datetime
    updated_at: datetime
    metadata_json: dict[str, Any]


class ActivationRequest(BaseModel):
    """Request payload for spreading activation."""

    strength: float = Field(default=1.0, ge=0.0, le=1.0)


class ActivationResponse(BaseModel):
    """Spreading activation result."""

    source_id: str
    initial_strength: float
    max_hops: int
    activations: dict[str, float]

    @field_validator("activations")
    @classmethod
    def round_activations(cls, value: dict[str, float]) -> dict[str, float]:
        """Round activation values for stable API output.

        Args:
            value: Raw activation map.

        Returns:
            dict[str, float]: Rounded activation map.
        """
        return {key: round(strength, 6) for key, strength in value.items()}
