"""Working memory manager for active thought objects."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime

from app.models.schemas import ThoughtCreate, ThoughtRead

WORKING_MEMORY_MAX_SIZE = 7
SALIENCE_DECAY_PER_HOUR = 0.05


class WorkingMemoryManager:
    """Manage a bounded set of active thoughts with salience decay."""

    def __init__(self, max_size: int = WORKING_MEMORY_MAX_SIZE) -> None:
        """Initialize an empty working memory store.

        Args:
            max_size: Maximum number of active thoughts allowed.
        """
        self.max_size = max_size
        self._thoughts: dict[str, ThoughtRead] = {}

    def add_thought(
        self,
        payload: ThoughtCreate,
        now: datetime | None = None,
        thought_id: str | None = None,
    ) -> ThoughtRead:
        """Add a thought to working memory, evicting the lowest salience if full.

        Args:
            payload: Thought creation payload.
            now: Reference time used for timestamps and decay.
            thought_id: Optional deterministic identifier for tests.

        Returns:
            ThoughtRead: The stored thought object.
        """
        current_time = now or datetime.now()
        self.decay_salience(current_time)

        if len(self._thoughts) >= self.max_size:
            self._evict_lowest_salience()

        thought = ThoughtRead(
            id=thought_id or str(uuid.uuid4()),
            content=payload.content,
            source=payload.source,
            salience=payload.salience,
            emotional_weight=payload.emotional_weight,
            novelty=payload.novelty,
            resolved=payload.resolved,
            created_at=current_time,
            expires_at=payload.expires_at,
            times_resurfaced=0,
            last_accessed=current_time,
            metadata_json=deepcopy(payload.metadata_json),
        )
        self._thoughts[thought.id] = thought
        return thought.model_copy(deep=True)

    def remove_thought(self, thought_id: str) -> bool:
        """Remove a thought from working memory.

        Args:
            thought_id: Identifier of the thought to remove.

        Returns:
            bool: True when the thought existed and was removed.
        """
        return self._thoughts.pop(thought_id, None) is not None

    def update_salience(
        self,
        thought_id: str,
        salience: float,
        now: datetime | None = None,
    ) -> ThoughtRead | None:
        """Update salience for a thought in working memory.

        Args:
            thought_id: Identifier of the thought to update.
            salience: New salience value.
            now: Optional timestamp for last_accessed.

        Returns:
            ThoughtRead | None: Updated thought, or None if not found.
        """
        thought = self._thoughts.get(thought_id)
        if thought is None:
            return None

        current_time = now or datetime.now()
        updated = thought.model_copy(
            update={
                "salience": salience,
                "last_accessed": current_time,
            },
            deep=True,
        )
        self._thoughts[thought_id] = updated
        return updated.model_copy(deep=True)

    def get_active_thoughts(self, now: datetime | None = None) -> list[ThoughtRead]:
        """Return unresolved, unexpired thoughts sorted by salience descending.

        Args:
            now: Reference time used for expiry checks and decay.

        Returns:
            list[ThoughtRead]: Active thoughts in working memory.
        """
        current_time = now or datetime.now()
        self.decay_salience(current_time)

        active = [
            thought.model_copy(deep=True)
            for thought in self._thoughts.values()
            if self._is_active(thought, current_time)
        ]
        active.sort(key=lambda thought: (-thought.salience, thought.id))
        return active

    def decay_salience(self, now: datetime | None = None) -> None:
        """Apply linear salience decay based on time since last access.

        Args:
            now: Reference time for decay calculation.

        Returns:
            None
        """
        current_time = now or datetime.now()

        for thought_id, thought in list(self._thoughts.items()):
            elapsed_hours = (
                current_time - thought.last_accessed
            ).total_seconds() / 3600.0
            if elapsed_hours <= 0:
                continue

            decayed_salience = max(
                0.0,
                thought.salience - (SALIENCE_DECAY_PER_HOUR * elapsed_hours),
            )
            self._thoughts[thought_id] = thought.model_copy(
                update={
                    "salience": decayed_salience,
                    "last_accessed": current_time,
                },
                deep=True,
            )

    def size(self) -> int:
        """Return the number of thoughts currently held in working memory.

        Returns:
            int: Count of stored thoughts.
        """
        return len(self._thoughts)

    def _evict_lowest_salience(self) -> None:
        """Remove the lowest-salience thought, breaking ties by thought id."""
        if not self._thoughts:
            return

        victim_id = min(
            self._thoughts.values(),
            key=lambda thought: (thought.salience, thought.id),
        ).id
        del self._thoughts[victim_id]

    @staticmethod
    def _is_active(thought: ThoughtRead, now: datetime) -> bool:
        """Check whether a thought is unresolved and not expired.

        Args:
            thought: Thought to evaluate.
            now: Reference time for expiry comparison.

        Returns:
            bool: True when the thought is active.
        """
        if thought.resolved:
            return False
        if thought.expires_at is not None and thought.expires_at <= now:
            return False
        return True
