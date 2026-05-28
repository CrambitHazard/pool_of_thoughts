"""Shared types for associative thought graphs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.graph_types import RelationType


@dataclass(frozen=True)
class ThoughtLink:
    """Directed edge between two thought nodes."""

    id: str
    source_id: str
    target_id: str
    relation: RelationType
    weight: float
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActivationResult:
    """Spreading activation output keyed by thought id."""

    source_id: str
    initial_strength: float
    activations: dict[str, float] = field(default_factory=dict)
    max_hops: int = 0

    def top(self, limit: int = 10) -> list[tuple[str, float]]:
        """Return the strongest activations excluding the source.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            list[tuple[str, float]]: Thought ids and activation strengths.
        """
        ranked = sorted(
            (
                (thought_id, strength)
                for thought_id, strength in self.activations.items()
                if thought_id != self.source_id
            ),
            key=lambda item: (-abs(item[1]), item[0]),
        )
        return ranked[:limit]


@dataclass
class GraphThemeCluster:
    """Mechanically detected group of recurring themes."""

    id: str
    label: str
    thought_ids: list[str]
    cohesion: float
    metadata_json: dict[str, Any] = field(default_factory=dict)
