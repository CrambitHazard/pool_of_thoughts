"""Backlog queue for thoughts outside working memory."""

from __future__ import annotations

from datetime import datetime

from app.memory.thought_utils import apply_salience_decay, is_active_thought
from app.memory.working_memory import SALIENCE_DECAY_PER_HOUR
from app.models.schemas import ThoughtRead


class BacklogMemoryManager:
    """Queue-like store for displaced or deferred thoughts."""

    def __init__(self) -> None:
        """Initialize an empty backlog store."""
        self._thoughts: dict[str, ThoughtRead] = {}

    def enqueue(self, thought: ThoughtRead) -> ThoughtRead:
        """Add or replace a thought in the backlog.

        Args:
            thought: Thought object to store.

        Returns:
            ThoughtRead: Stored copy of the thought.
        """
        stored = thought.model_copy(deep=True)
        self._thoughts[stored.id] = stored
        return stored.model_copy(deep=True)

    def remove(self, thought_id: str) -> bool:
        """Remove a thought from the backlog.

        Args:
            thought_id: Identifier of the thought to remove.

        Returns:
            bool: True when the thought existed and was removed.
        """
        return self._thoughts.pop(thought_id, None) is not None

    def get(self, thought_id: str) -> ThoughtRead | None:
        """Fetch a backlog thought by identifier.

        Args:
            thought_id: Thought identifier.

        Returns:
            ThoughtRead | None: Stored thought when found.
        """
        thought = self._thoughts.get(thought_id)
        if thought is None:
            return None
        return thought.model_copy(deep=True)

    def list_active(self, now: datetime | None = None) -> list[ThoughtRead]:
        """Return unresolved, unexpired backlog thoughts.

        Args:
            now: Reference time for active filtering.

        Returns:
            list[ThoughtRead]: Active backlog thoughts sorted by id.
        """
        current_time = now or datetime.now()
        active = [
            thought.model_copy(deep=True)
            for thought in self._thoughts.values()
            if is_active_thought(thought, current_time)
        ]
        active.sort(key=lambda thought: thought.id)
        return active

    def decay_salience(self, now: datetime | None = None) -> int:
        """Apply salience decay to all backlog thoughts.

        Args:
            now: Reference time for decay calculation.

        Returns:
            int: Number of thoughts updated.
        """
        current_time = now or datetime.now()
        updated = 0

        for thought_id, thought in list(self._thoughts.items()):
            decayed = apply_salience_decay(thought, current_time, SALIENCE_DECAY_PER_HOUR)
            if decayed.salience != thought.salience or decayed.last_accessed != thought.last_accessed:
                updated += 1
            self._thoughts[thought_id] = decayed

        return updated

    def remove_expired(self, now: datetime | None = None) -> list[ThoughtRead]:
        """Remove expired or resolved thoughts from the backlog.

        Args:
            now: Reference time for expiry evaluation.

        Returns:
            list[ThoughtRead]: Removed thoughts in deterministic order.
        """
        current_time = now or datetime.now()
        removed: list[ThoughtRead] = []

        for thought_id in sorted(self._thoughts):
            thought = self._thoughts[thought_id]
            if is_active_thought(thought, current_time):
                continue
            removed.append(self._thoughts.pop(thought_id).model_copy(deep=True))

        return removed

    def size(self) -> int:
        """Return the number of thoughts currently in the backlog.

        Returns:
            int: Backlog count.
        """
        return len(self._thoughts)
