"""Attention arbitration for working-memory competition."""

from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.cognitive.conflict import ThoughtConflictResolver
from app.cognitive.similarity import ThoughtSimilarity
from app.memory.backlog import BacklogMemoryManager
from app.memory.working_memory import WorkingMemoryManager
from app.models.schemas import ThoughtCreate, ThoughtRead

INTERRUPTION_SALIENCE_THRESHOLD = 0.75
INTERRUPTION_MARGIN = 0.15
MERGE_SALIENCE_BOOST = 0.05

AttentionAction = Literal["added", "merged", "interrupted", "replaced"]


@dataclass
class AttentionResult:
    """Outcome of attentional competition for a thought."""

    action: AttentionAction
    thought: ThoughtRead
    displaced: list[ThoughtRead] = field(default_factory=list)
    conflict_pairs: list[tuple[str, str]] = field(default_factory=list)
    merged_into: str | None = None


class AttentionArbitrator:
    """Resolve competition for bounded working-memory slots."""

    def __init__(
        self,
        similarity: ThoughtSimilarity | None = None,
        conflict_resolver: ThoughtConflictResolver | None = None,
        interruption_threshold: float = INTERRUPTION_SALIENCE_THRESHOLD,
        interruption_margin: float = INTERRUPTION_MARGIN,
    ) -> None:
        """Initialize the attention arbitrator.

        Args:
            similarity: Similarity service for merge detection.
            conflict_resolver: Resolver for contradictory thoughts.
            interruption_threshold: Minimum salience required to interrupt.
            interruption_margin: Lead over the weakest occupant required to interrupt.
        """
        self.similarity = similarity or ThoughtSimilarity()
        self.conflict_resolver = conflict_resolver or ThoughtConflictResolver(
            similarity=self.similarity
        )
        self.interruption_threshold = interruption_threshold
        self.interruption_margin = interruption_margin

    def arbitrate(
        self,
        working_memory: WorkingMemoryManager,
        backlog: BacklogMemoryManager,
        payload: ThoughtCreate,
        now: datetime | None = None,
        thought_id: str | None = None,
    ) -> AttentionResult:
        """Compete for working-memory placement using merge and interruption rules.

        Args:
            working_memory: Active working memory manager.
            backlog: Backlog queue for displaced thoughts.
            payload: Incoming thought candidate.
            now: Reference time for timestamps and decay.
            thought_id: Optional deterministic identifier for tests.

        Returns:
            AttentionResult: Final placement outcome.
        """
        current_time = now or datetime.now()
        working_memory.decay_salience(current_time)

        pending = self._build_pending_thought(payload, current_time, thought_id)
        existing = working_memory.all_thoughts()

        conflict_result = self.conflict_resolver.resolve([*existing, pending])
        resolved_by_id = {
            getattr(thought, "id"): thought
            for thought in conflict_result.thoughts
            if getattr(thought, "id", None)
        }

        for thought in existing:
            updated = resolved_by_id.get(thought.id)
            if updated is not None and isinstance(updated, ThoughtRead):
                working_memory.set_thought(updated)

        pending = resolved_by_id.get(pending.id, pending)
        if not isinstance(pending, ThoughtRead):
            pending = self._build_pending_thought(payload, current_time, thought_id)

        merge_target, _score = self.similarity.should_merge(
            pending,
            working_memory.all_thoughts(),
        )
        if merge_target is not None:
            merged = self._merge_thoughts(merge_target, pending, current_time)
            working_memory.set_thought(merged)
            return AttentionResult(
                action="merged",
                thought=merged,
                conflict_pairs=conflict_result.conflict_pairs,
                merged_into=merge_target.id,
            )

        if working_memory.size() < working_memory.max_size:
            working_memory.set_thought(pending)
            return AttentionResult(
                action="added",
                thought=pending.model_copy(deep=True),
                conflict_pairs=conflict_result.conflict_pairs,
            )

        weakest = working_memory.get_weakest()
        if weakest is None:
            working_memory.set_thought(pending)
            return AttentionResult(
                action="added",
                thought=pending.model_copy(deep=True),
                conflict_pairs=conflict_result.conflict_pairs,
            )

        interrupted = self._should_interrupt(pending, weakest)
        evicted = working_memory.pop_thought(weakest.id) or weakest

        displaced = [evicted.model_copy(deep=True)]
        backlog.enqueue(evicted)
        working_memory.set_thought(pending)

        return AttentionResult(
            action="interrupted" if interrupted else "replaced",
            thought=pending.model_copy(deep=True),
            displaced=displaced,
            conflict_pairs=conflict_result.conflict_pairs,
        )

    def _should_interrupt(self, incoming: ThoughtRead, weakest: ThoughtRead) -> bool:
        """Decide whether an incoming thought interrupts the weakest occupant.

        Args:
            incoming: Incoming thought candidate.
            weakest: Lowest-salience working-memory thought.

        Returns:
            bool: True when the incoming thought qualifies as an interruption.
        """
        return incoming.salience >= self.interruption_threshold and (
            incoming.salience >= weakest.salience + self.interruption_margin
        )

    @staticmethod
    def _build_pending_thought(
        payload: ThoughtCreate,
        now: datetime,
        thought_id: str | None,
    ) -> ThoughtRead:
        """Build a pending thought object before placement.

        Args:
            payload: Incoming thought payload.
            now: Timestamp for created_at and last_accessed.
            thought_id: Optional deterministic identifier.

        Returns:
            ThoughtRead: Pending thought candidate.
        """
        return ThoughtRead(
            id=thought_id or str(uuid.uuid4()),
            content=payload.content,
            source=payload.source,
            salience=payload.salience,
            emotional_weight=payload.emotional_weight,
            novelty=payload.novelty,
            resolved=payload.resolved,
            created_at=now,
            expires_at=payload.expires_at,
            times_resurfaced=0,
            last_accessed=now,
            metadata_json=deepcopy(payload.metadata_json),
        )

    @staticmethod
    def _merge_thoughts(
        existing: ThoughtRead,
        incoming: ThoughtRead,
        now: datetime,
    ) -> ThoughtRead:
        """Merge similar thoughts into one working-memory occupant.

        Args:
            existing: Thought already in working memory.
            incoming: Incoming similar thought.
            now: Timestamp for last_accessed.

        Returns:
            ThoughtRead: Merged thought object.
        """
        if incoming.content.strip().lower() == existing.content.strip().lower():
            merged_content = existing.content
        elif incoming.content.lower() in existing.content.lower():
            merged_content = existing.content
        elif existing.content.lower() in incoming.content.lower():
            merged_content = incoming.content
        else:
            merged_content = f"{existing.content}; {incoming.content}"

        metadata = deepcopy(existing.metadata_json)
        metadata["merged"] = True
        metadata["merged_sources"] = sorted(
            {
                *metadata.get("merged_sources", []),
                existing.source,
                incoming.source,
            }
        )

        return existing.model_copy(
            update={
                "content": merged_content,
                "salience": min(
                    1.0,
                    max(existing.salience, incoming.salience) + MERGE_SALIENCE_BOOST,
                ),
                "emotional_weight": max(
                    existing.emotional_weight,
                    incoming.emotional_weight,
                ),
                "novelty": (existing.novelty + incoming.novelty) / 2.0,
                "last_accessed": now,
                "metadata_json": metadata,
            },
            deep=True,
        )
