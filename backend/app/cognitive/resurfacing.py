"""Mechanical rules for resurfacing backlog thoughts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.memory.thought_utils import is_active_thought
from app.models.schemas import ThoughtRead

NOVELTY_THRESHOLD = 0.6
REPEATED_RELEVANCE_MIN_RESURFACES = 1
REPEATED_RELEVANCE_MIN_SALIENCE = 0.2


@dataclass(frozen=True)
class ResurfacingStrategy:
    """Deterministic rules for returning backlog thoughts to working memory."""

    novelty_threshold: float = NOVELTY_THRESHOLD
    repeated_relevance_min_resurfaces: int = REPEATED_RELEVANCE_MIN_RESURFACES
    repeated_relevance_min_salience: float = REPEATED_RELEVANCE_MIN_SALIENCE

    def should_resurface(self, thought: ThoughtRead, now: datetime) -> bool:
        """Decide whether a backlog thought should re-enter working memory.

        Args:
            thought: Candidate backlog thought.
            now: Reference time for active checks.

        Returns:
            bool: True when the thought should resurface.
        """
        if not is_active_thought(thought, now):
            return False

        if thought.novelty >= self.novelty_threshold:
            return True

        if (
            thought.times_resurfaced >= self.repeated_relevance_min_resurfaces
            and thought.salience >= self.repeated_relevance_min_salience
        ):
            return True

        return False

    def score(self, thought: ThoughtRead) -> float:
        """Rank resurfacing candidates deterministically.

        Args:
            thought: Candidate backlog thought.

        Returns:
            float: Higher values indicate stronger resurfacing priority.
        """
        return (
            (thought.novelty * 0.5)
            + (thought.salience * 0.3)
            + (thought.emotional_weight * 0.1)
            + (thought.times_resurfaced * 0.05)
        )

    def rank_candidates(
        self,
        thoughts: list[ThoughtRead],
        now: datetime,
    ) -> list[ThoughtRead]:
        """Return eligible backlog thoughts ordered by resurfacing priority.

        Args:
            thoughts: Backlog thoughts to evaluate.
            now: Reference time for active checks.

        Returns:
            list[ThoughtRead]: Filtered and sorted resurfacing candidates.
        """
        candidates = [
            thought for thought in thoughts if self.should_resurface(thought, now)
        ]
        candidates.sort(key=lambda thought: (-self.score(thought), thought.id))
        return candidates
