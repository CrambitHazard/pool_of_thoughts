"""Periodic reflective cognition loop."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from app.memory.consolidation import ConsolidationResult, ConsolidationService

logger = logging.getLogger(__name__)


@dataclass
class ReflectionResult:
    """Summary of one reflection cycle."""

    consolidation: ConsolidationResult = field(default_factory=ConsolidationResult)


class ReflectionEngine:
    """Run periodic reflection and long-term memory consolidation."""

    def __init__(
        self,
        consolidation_service: ConsolidationService,
        interval_minutes: float | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialize the reflection engine.

        Args:
            consolidation_service: Service that consolidates recent thoughts.
            interval_minutes: Minutes between reflection cycles.
            clock: Optional injectable clock for deterministic tests.
        """
        self.consolidation_service = consolidation_service
        self.interval_minutes = (
            interval_minutes
            if interval_minutes is not None
            else consolidation_service.settings.reflection_interval_minutes
        )
        self._clock = clock or datetime.now
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self.cycle_count = 0

    @property
    def interval_seconds(self) -> float:
        """Return the reflection interval in seconds.

        Returns:
            float: Seconds between scheduled reflection cycles.
        """
        return self.interval_minutes * 60.0

    async def reflect(self, now: datetime | None = None) -> ReflectionResult:
        """Run one reflection and consolidation cycle.

        Args:
            now: Reference time for consolidation.

        Returns:
            ReflectionResult: Summary of the reflection cycle.
        """
        consolidation = await self.consolidation_service.consolidate(now=now)
        self.cycle_count += 1
        return ReflectionResult(consolidation=consolidation)

    def start(self) -> None:
        """Start the periodic reflection loop.

        Returns:
            None
        """
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_forever(), name="reflection-engine")

    async def stop(self) -> None:
        """Stop the periodic reflection loop.

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
        """Execute scheduled reflection cycles until stopped.

        Returns:
            None

        Raises:
            asyncio.CancelledError: When the engine is stopped.
        """
        while self._running:
            try:
                result = await self.reflect()
                logger.info(
                    "Reflection cycle %s: created=%s updated=%s reviewed=%s",
                    self.cycle_count,
                    result.consolidation.created,
                    result.consolidation.updated,
                    result.consolidation.reviewed_thoughts,
                )
            except Exception:
                logger.exception("Reflection cycle failed")

            await asyncio.sleep(self.interval_seconds)
