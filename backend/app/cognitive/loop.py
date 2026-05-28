"""Background cognitive loop orchestration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from app.cognitive.resurfacing import ResurfacingStrategy
from app.memory.backlog import BacklogMemoryManager
from app.memory.working_memory import WorkingMemoryManager
from app.models.schemas import ThoughtCreate, ThoughtRead

logger = logging.getLogger(__name__)


@dataclass
class CognitiveLoopTickResult:
    """Summary of one cognitive loop iteration."""

    backlog_decayed: int = 0
    expired_removed: int = 0
    resurfaced: list[str] = field(default_factory=list)
    evicted_to_backlog: list[str] = field(default_factory=list)


class CognitiveLoop:
    """Periodic attention loop for decay, cleanup, and resurfacing."""

    def __init__(
        self,
        working_memory: WorkingMemoryManager,
        backlog: BacklogMemoryManager,
        strategy: ResurfacingStrategy | None = None,
        interval_minutes: float = 5.0,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialize the cognitive loop.

        Args:
            working_memory: Active working memory manager.
            backlog: Backlog queue for displaced thoughts.
            strategy: Resurfacing decision rules.
            interval_minutes: Minutes between background loop iterations.
            clock: Optional injectable clock for deterministic tests.
        """
        self.working_memory = working_memory
        self.backlog = backlog
        self.strategy = strategy or ResurfacingStrategy()
        self.interval_minutes = interval_minutes
        self._clock = clock or datetime.now
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self.tick_count = 0

    @property
    def interval_seconds(self) -> float:
        """Return the loop interval in seconds.

        Returns:
            float: Seconds between scheduled ticks.
        """
        return self.interval_minutes * 60.0

    def ingest_thought(
        self,
        payload: ThoughtCreate,
        now: datetime | None = None,
        thought_id: str | None = None,
    ) -> ThoughtRead:
        """Add a thought to working memory and queue any eviction to backlog.

        Args:
            payload: Thought creation payload.
            now: Reference time for timestamps and decay.
            thought_id: Optional deterministic identifier for tests.

        Returns:
            ThoughtRead: Thought stored in working memory.
        """
        current_time = now or self._clock()
        thought, evicted = self.working_memory.add_thought_with_eviction(
            payload,
            now=current_time,
            thought_id=thought_id,
        )
        if evicted is not None:
            self.backlog.enqueue(evicted)
        return thought

    def tick(self, now: datetime | None = None) -> CognitiveLoopTickResult:
        """Run one cognitive loop iteration.

        Args:
            now: Reference time for decay, expiry, and resurfacing.

        Returns:
            CognitiveLoopTickResult: Summary of actions taken this tick.
        """
        current_time = now or self._clock()
        result = CognitiveLoopTickResult()

        self.working_memory.decay_salience(current_time)
        result.backlog_decayed = self.backlog.decay_salience(current_time)

        expired_working = self.working_memory.remove_inactive(current_time)
        expired_backlog = self.backlog.remove_expired(current_time)
        result.expired_removed = len(expired_working) + len(expired_backlog)

        candidates = self.strategy.rank_candidates(
            self.backlog.list_active(current_time),
            current_time,
        )
        for candidate in candidates:
            if not self.backlog.remove(candidate.id):
                continue

            restored, evicted = self.working_memory.restore_thought(
                candidate,
                now=current_time,
            )
            result.resurfaced.append(restored.id)

            if evicted is not None:
                self.backlog.enqueue(evicted)
                result.evicted_to_backlog.append(evicted.id)

        self.tick_count += 1
        return result

    def start(self) -> None:
        """Start the background scheduler loop.

        Returns:
            None
        """
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_forever(), name="cognitive-loop")

    async def stop(self) -> None:
        """Stop the background scheduler loop.

        Returns:
            None
        """
        self._running = False
        if self._task is None:
            return

        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def _run_forever(self) -> None:
        """Execute scheduled cognitive ticks until stopped.

        Returns:
            None

        Raises:
            asyncio.CancelledError: When the loop is stopped.
        """
        while self._running:
            try:
                result = self.tick()
                logger.info(
                    "Cognitive tick %s: resurfaced=%s expired=%s",
                    self.tick_count,
                    result.resurfaced,
                    result.expired_removed,
                )
            except Exception:
                logger.exception("Cognitive loop tick failed")

            await asyncio.sleep(self.interval_seconds)
