"""Protocols for pluggable contextual cognition."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.cognitive.context.types import ActivityRecord, ContextState, ContextWindow
from app.models.schemas import ThoughtRead


class ContextProvider(Protocol):
    """Produces contextual signals for one temporal window."""

    name: str
    window: ContextWindow

    def collect(
        self,
        activities: list[ActivityRecord],
        thoughts: list[ThoughtRead],
        now: datetime,
    ) -> dict[str, float]:
        """Collect signal strengths for this provider.

        Args:
            activities: Activity records within the provider window.
            thoughts: Active thoughts available for inference.
            now: Reference timestamp.

        Returns:
            dict[str, float]: Signal name to strength mapping.
        """


class SalienceRule(Protocol):
    """Adjusts thought salience from contextual state."""

    name: str

    def adjust(
        self,
        thought: ThoughtRead,
        state: ContextState,
        activities: list[ActivityRecord],
    ) -> tuple[float, list[str]]:
        """Compute a salience delta for one thought.

        Args:
            thought: Thought being evaluated.
            state: Aggregated contextual signals.
            activities: Relevant activity records.

        Returns:
            tuple[float, list[str]]: Delta and human-readable reasons.
        """
