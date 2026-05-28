"""Working memory manager for active thought objects."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime

from app.memory.thought_utils import apply_salience_decay, is_active_thought
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
        thought, _evicted = self.add_thought_with_eviction(payload, now, thought_id)
        return thought

    def add_thought_with_eviction(
        self,
        payload: ThoughtCreate,
        now: datetime | None = None,
        thought_id: str | None = None,
    ) -> tuple[ThoughtRead, ThoughtRead | None]:
        """Add a thought and return any evicted thought.

        Args:
            payload: Thought creation payload.
            now: Reference time used for timestamps and decay.
            thought_id: Optional deterministic identifier for tests.

        Returns:
            tuple[ThoughtRead, ThoughtRead | None]: Added thought and optional evictee.
        """
        current_time = now or datetime.now()
        self.decay_salience(current_time)

        evicted = None
        if len(self._thoughts) >= self.max_size:
            evicted = self._evict_lowest_salience()

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
        return thought.model_copy(deep=True), evicted

    def restore_thought(
        self,
        thought: ThoughtRead,
        now: datetime | None = None,
    ) -> tuple[ThoughtRead, ThoughtRead | None]:
        """Return a backlog thought to working memory.

        Args:
            thought: Thought to restore.
            now: Reference time for timestamps.

        Returns:
            tuple[ThoughtRead, ThoughtRead | None]: Restored thought and optional evictee.
        """
        current_time = now or datetime.now()
        evicted = None

        if thought.id not in self._thoughts and len(self._thoughts) >= self.max_size:
            evicted = self._evict_lowest_salience()

        restored = thought.model_copy(
            update={
                "times_resurfaced": thought.times_resurfaced + 1,
                "last_accessed": current_time,
            },
            deep=True,
        )
        self._thoughts[restored.id] = restored
        return restored.model_copy(deep=True), evicted

    def remove_thought(self, thought_id: str) -> bool:
        """Remove a thought from working memory.

        Args:
            thought_id: Identifier of the thought to remove.

        Returns:
            bool: True when the thought existed and was removed.
        """
        return self._thoughts.pop(thought_id, None) is not None

    def pop_thought(self, thought_id: str) -> ThoughtRead | None:
        """Remove and return a thought from working memory.

        Args:
            thought_id: Identifier of the thought to remove.

        Returns:
            ThoughtRead | None: Removed thought when found.
        """
        thought = self._thoughts.pop(thought_id, None)
        if thought is None:
            return None
        return thought.model_copy(deep=True)

    def remove_inactive(self, now: datetime | None = None) -> list[ThoughtRead]:
        """Remove expired or resolved thoughts from working memory.

        Args:
            now: Reference time for inactive evaluation.

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
            if is_active_thought(thought, current_time)
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
            self._thoughts[thought_id] = apply_salience_decay(
                thought,
                current_time,
                SALIENCE_DECAY_PER_HOUR,
            )

    def get(self, thought_id: str) -> ThoughtRead | None:
        """Fetch a working-memory thought by identifier.

        Args:
            thought_id: Thought identifier.

        Returns:
            ThoughtRead | None: Stored thought when found.
        """
        thought = self._thoughts.get(thought_id)
        if thought is None:
            return None
        return thought.model_copy(deep=True)

    def all_thoughts(self) -> list[ThoughtRead]:
        """Return all thoughts currently held in working memory.

        Returns:
            list[ThoughtRead]: Stored thoughts sorted by id.
        """
        thoughts = [thought.model_copy(deep=True) for thought in self._thoughts.values()]
        thoughts.sort(key=lambda thought: thought.id)
        return thoughts

    def set_thought(self, thought: ThoughtRead) -> ThoughtRead:
        """Insert or replace a thought in working memory.

        Args:
            thought: Thought object to store.

        Returns:
            ThoughtRead: Stored copy of the thought.
        """
        stored = thought.model_copy(deep=True)
        self._thoughts[stored.id] = stored
        return stored.model_copy(deep=True)

    def get_weakest(self) -> ThoughtRead | None:
        """Return the lowest-salience thought in working memory.

        Returns:
            ThoughtRead | None: Weakest thought when memory is not empty.
        """
        if not self._thoughts:
            return None

        weakest = min(
            self._thoughts.values(),
            key=lambda thought: (thought.salience, thought.id),
        )
        return weakest.model_copy(deep=True)

    def size(self) -> int:
        """Return the number of thoughts currently held in working memory.

        Returns:
            int: Count of stored thoughts.
        """
        return len(self._thoughts)

    def _evict_lowest_salience(self) -> ThoughtRead | None:
        """Remove and return the lowest-salience thought.

        Returns:
            ThoughtRead | None: Evicted thought, if any were present.
        """
        if not self._thoughts:
            return None

        victim = min(
            self._thoughts.values(),
            key=lambda thought: (thought.salience, thought.id),
        )
        return self._thoughts.pop(victim.id).model_copy(deep=True)
