"""In-process cognition runtime for API-driven interaction."""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.cognitive.arbitrator import AttentionResult
from app.cognitive.loop import CognitiveLoop, CognitiveLoopTickResult
from app.cognitive.thought_extraction import ThoughtExtractionService
from app.config.settings import get_settings
from app.memory.backlog import BacklogMemoryManager
from app.memory.graph import ThoughtGraph
from app.memory.working_memory import WORKING_MEMORY_MAX_SIZE, WorkingMemoryManager
from app.models.schemas import ThoughtCreate, ThoughtRead

ActivityType = Literal[
    "thought_added",
    "thought_merged",
    "thought_interrupted",
    "thought_replaced",
    "thought_evicted",
    "thought_resurfaced",
    "tick_complete",
    "reflection_complete",
    "input_received",
    "graph_activated",
]


@dataclass
class ActivityEvent:
    """Single cognitive activity entry for the live feed."""

    id: str
    type: ActivityType
    message: str
    timestamp: datetime
    thought_id: str | None = None
    source_panel: str | None = None
    target_panel: str | None = None


@dataclass
class CognitionState:
    """Snapshot of current cognitive memory layers."""

    working_memory: list[ThoughtRead] = field(default_factory=list)
    backlog: list[ThoughtRead] = field(default_factory=list)
    activity: list[ActivityEvent] = field(default_factory=list)
    working_capacity: int = WORKING_MEMORY_MAX_SIZE
    tick_count: int = 0


class CognitionRuntime:
    """Manage live cognition state and activity logging."""

    def __init__(
        self,
        extraction_service: ThoughtExtractionService | None = None,
        thought_graph: ThoughtGraph | None = None,
        max_activity: int = 50,
    ) -> None:
        """Initialize runtime memory stores and loops.

        Args:
            extraction_service: Optional thought extraction service.
            thought_graph: Optional associative graph for linking and activation.
            max_activity: Maximum activity feed entries to retain.
        """
        self.working_memory = WorkingMemoryManager()
        self.backlog = BacklogMemoryManager()
        self.loop = CognitiveLoop(self.working_memory, self.backlog)
        self.extraction_service = extraction_service
        self.thought_graph = thought_graph
        self.max_activity = max_activity
        self._activity: deque[ActivityEvent] = deque(maxlen=max_activity)

    def get_state(self, now: datetime | None = None) -> CognitionState:
        """Return the current cognitive state snapshot.

        Args:
            now: Reference time for active thought filtering.

        Returns:
            CognitionState: Current memory layers and activity feed.
        """
        current_time = now or datetime.now()
        return CognitionState(
            working_memory=self.working_memory.get_active_thoughts(current_time),
            backlog=self.backlog.list_active(current_time),
            activity=list(self._activity),
            working_capacity=self.working_memory.max_size,
            tick_count=self.loop.tick_count,
        )

    async def ingest_message(self, message: str) -> CognitionState:
        """Extract and ingest thoughts from a raw user message.

        Args:
            message: Raw user input.

        Returns:
            CognitionState: Updated cognitive state.

        Raises:
            RuntimeError: When extraction service is not configured.
        """
        if self.extraction_service is None:
            raise RuntimeError("Thought extraction service is not configured.")

        current_time = datetime.now()
        self._log(
            "input_received",
            f"Input received: {message[:80]}",
            timestamp=current_time,
        )

        extraction = await self.extraction_service.extract_from_message(message)
        for index, payload in enumerate(extraction.to_thought_creates()):
            thought_id = f"extracted-{uuid.uuid4()}" if index else f"primary-{uuid.uuid4()}"
            result = self._ingest_with_logging(payload, thought_id=thought_id, now=current_time)

        return self.get_state(current_time)

    def ingest_thought(self, payload: ThoughtCreate) -> CognitionState:
        """Ingest a structured thought directly.

        Args:
            payload: Thought creation payload.

        Returns:
            CognitionState: Updated cognitive state.
        """
        current_time = datetime.now()
        self._ingest_with_logging(payload, thought_id=str(uuid.uuid4()), now=current_time)
        return self.get_state(current_time)

    def run_tick(self, now: datetime | None = None) -> CognitionState:
        """Run one cognitive loop tick.

        Args:
            now: Reference time for the tick.

        Returns:
            CognitionState: Updated cognitive state.
        """
        current_time = now or datetime.now()
        before_working = {thought.id for thought in self.working_memory.all_thoughts()}
        before_backlog = {thought.id for thought in self.backlog.list_active(current_time)}

        result = self.loop.tick(now=current_time)
        self._log_tick_events(result, before_working, before_backlog, current_time)
        self._spread_activation(current_time)

        return self.get_state(current_time)

    def log_reflection(self, created: list[str], updated: list[str]) -> None:
        """Record reflection activity in the feed.

        Args:
            created: New abstraction ids.
            updated: Updated abstraction ids.

        Returns:
            None
        """
        summary = f"Reflection stored {len(created)} new and updated {len(updated)} abstractions"
        self._log("reflection_complete", summary)

    def _ingest_with_logging(
        self,
        payload: ThoughtCreate,
        thought_id: str,
        now: datetime,
    ) -> AttentionResult:
        """Ingest a thought and emit activity events.

        Args:
            payload: Thought creation payload.
            thought_id: Identifier for the incoming thought.
            now: Reference timestamp.

        Returns:
            AttentionResult: Attention arbitration outcome.
        """
        result = self.loop.arbitrator.arbitrate(
            self.working_memory,
            self.backlog,
            payload,
            now=now,
            thought_id=thought_id,
        )
        self._log_attention_result(result)
        self._register_graph_links(result.thought, now)
        return result

    def _log_attention_result(self, result: AttentionResult) -> None:
        """Translate attention results into feed events.

        Args:
            result: Attention arbitration outcome.

        Returns:
            None
        """
        if result.action == "merged":
            self._log(
                "thought_merged",
                f"Merged into active thought: {result.thought.content[:72]}",
                thought_id=result.thought.id,
                source_panel="input",
                target_panel="workspace",
            )
            return

        if result.action == "added":
            self._log(
                "thought_added",
                f"Added to workspace: {result.thought.content[:72]}",
                thought_id=result.thought.id,
                source_panel="input",
                target_panel="workspace",
            )
            return

        for displaced in result.displaced:
            self._log(
                "thought_evicted",
                f"Moved to backlog: {displaced.content[:72]}",
                thought_id=displaced.id,
                source_panel="workspace",
                target_panel="backlog",
            )

        event_type: ActivityType = (
            "thought_interrupted" if result.action == "interrupted" else "thought_replaced"
        )
        verb = "Interrupted workspace with" if result.action == "interrupted" else "Replaced slot with"
        self._log(
            event_type,
            f"{verb}: {result.thought.content[:72]}",
            thought_id=result.thought.id,
            source_panel="input",
            target_panel="workspace",
        )

    def _log_tick_events(
        self,
        result: CognitiveLoopTickResult,
        before_working: set[str],
        before_backlog: set[str],
        now: datetime,
    ) -> None:
        """Record cognitive loop tick events.

        Args:
            result: Tick result summary.
            before_working: Working-memory ids before the tick.
            before_backlog: Backlog ids before the tick.
            now: Tick timestamp.

        Returns:
            None
        """
        current_working = {thought.id for thought in self.working_memory.all_thoughts()}
        current_backlog = {thought.id for thought in self.backlog.list_active(now)}

        for thought_id in result.resurfaced:
            thought = self.working_memory.get(thought_id)
            content = thought.content[:72] if thought else thought_id
            self._log(
                "thought_resurfaced",
                f"Resurfaced into workspace: {content}",
                thought_id=thought_id,
                source_panel="backlog",
                target_panel="workspace",
            )

        for thought_id in result.evicted_to_backlog:
            if thought_id in before_working:
                continue
            thought = self.backlog.get(thought_id)
            content = thought.content[:72] if thought else thought_id
            self._log(
                "thought_evicted",
                f"Moved to backlog: {content}",
                thought_id=thought_id,
                source_panel="workspace",
                target_panel="backlog",
            )

        self._log(
            "tick_complete",
            (
                f"Tick {self.loop.tick_count}: resurfaced={len(result.resurfaced)} "
                f"expired={result.expired_removed}"
            ),
        )

        _ = (before_backlog, current_working, current_backlog)

    def _log(
        self,
        event_type: ActivityType,
        message: str,
        timestamp: datetime | None = None,
        thought_id: str | None = None,
        source_panel: str | None = None,
        target_panel: str | None = None,
    ) -> None:
        """Append an activity event.

        Args:
            event_type: Activity classification.
            message: Human-readable feed message.
            timestamp: Event timestamp.
            thought_id: Related thought identifier.
            source_panel: Origin panel label.
            target_panel: Destination panel label.

        Returns:
            None
        """
        self._activity.appendleft(
            ActivityEvent(
                id=str(uuid.uuid4()),
                type=event_type,
                message=message,
                timestamp=timestamp or datetime.now(),
                thought_id=thought_id,
                source_panel=source_panel,
                target_panel=target_panel,
            )
        )

    def _register_graph_links(self, thought: ThoughtRead, now: datetime) -> None:
        """Register a thought in the associative graph and auto-link similar items.

        Args:
            thought: Thought added to working memory.
            now: Reference timestamp.

        Returns:
            None
        """
        if self.thought_graph is None:
            return

        candidates = self.working_memory.all_thoughts() + self.backlog.list_active(now)
        self.thought_graph.auto_link_thought(thought, candidates, now=now)

    def _spread_activation(self, now: datetime) -> None:
        """Spread activation from the strongest working-memory thought.

        Args:
            now: Reference timestamp for backlog filtering.

        Returns:
            None
        """
        if self.thought_graph is None:
            return

        active = self.working_memory.get_active_thoughts(now)
        if not active:
            return

        source = max(active, key=lambda thought: (thought.salience, thought.id))
        activation = self.thought_graph.activate(source.id, strength=source.salience)
        settings = get_settings()
        boosted = self.thought_graph.apply_activation_to_salience(
            activation,
            self.working_memory.all_thoughts(),
            boost_factor=settings.graph_activation_boost_factor,
        )

        changed = 0
        for thought in boosted:
            existing = self.working_memory.get(thought.id)
            if existing is None or existing.salience == thought.salience:
                continue
            self.working_memory.set_thought(thought)
            changed += 1

        if changed:
            self._log(
                "graph_activated",
                f"Spread activation from {source.id[:8]} boosted {changed} linked thoughts",
                thought_id=source.id,
            )
