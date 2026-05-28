"""Attention arbitration tests."""

from datetime import datetime

import pytest

from app.cognitive.arbitrator import (
    INTERRUPTION_MARGIN,
    INTERRUPTION_SALIENCE_THRESHOLD,
    AttentionArbitrator,
)
from app.cognitive.conflict import ThoughtConflictResolver
from app.cognitive.similarity import ThoughtSimilarity
from app.memory.backlog import BacklogMemoryManager
from app.memory.working_memory import WorkingMemoryManager
from app.models.schemas import ThoughtCreate, ThoughtRead


NOW = datetime(2026, 5, 28, 12, 0, 0)


def make_payload(
    content: str,
    salience: float = 0.5,
    **kwargs: object,
) -> ThoughtCreate:
    """Build a thought payload for arbitration tests."""
    return ThoughtCreate(content=content, source="test", salience=salience, **kwargs)


def make_thought(
    thought_id: str,
    content: str,
    salience: float = 0.5,
) -> ThoughtRead:
    """Build a working-memory thought for unit tests."""
    return ThoughtRead(
        id=thought_id,
        content=content,
        source="test",
        salience=salience,
        emotional_weight=0.0,
        novelty=0.0,
        resolved=False,
        created_at=NOW,
        expires_at=None,
        times_resurfaced=0,
        last_accessed=NOW,
        metadata_json={},
    )


def test_similarity_detects_overlap() -> None:
    """Similarity uses lexical overlap heuristics."""
    service = ThoughtSimilarity()

    score = service.score(
        "finish memory model draft",
        "finish the memory model draft soon",
    )

    assert score >= 0.65


def test_similarity_finds_merge_target() -> None:
    """Similar incoming thoughts identify an existing merge target."""
    service = ThoughtSimilarity()
    existing = make_thought("a", "finish memory model draft", salience=0.6)
    candidate = make_payload("finish the memory model draft")

    target, score = service.should_merge(candidate, [existing])

    assert target is not None
    assert target.id == "a"
    assert score >= 0.65


def test_conflict_resolver_detects_negation() -> None:
    """Contradictory thoughts reduce each other's salience."""
    resolver = ThoughtConflictResolver()
    left = make_thought("yes", "enable memory persistence", salience=0.8)
    right = make_thought("no", "do not enable memory persistence", salience=0.8)

    result = resolver.resolve([left, right])

    assert result.conflict_pairs == [("no", "yes")]
    assert result.thoughts[0].salience == pytest.approx(0.65)
    assert result.thoughts[1].salience == pytest.approx(0.65)


def test_arbitrator_merges_similar_thoughts() -> None:
    """Similar thoughts merge instead of consuming a new slot."""
    working = WorkingMemoryManager(max_size=2)
    backlog = BacklogMemoryManager()
    arbitrator = AttentionArbitrator()
    working.set_thought(make_thought("existing", "finish memory model draft", 0.6))

    result = arbitrator.arbitrate(
        working,
        backlog,
        make_payload("finish the memory model draft", salience=0.7),
        now=NOW,
        thought_id="incoming",
    )

    assert result.action == "merged"
    assert working.size() == 1
    merged = working.get("existing")
    assert merged is not None
    assert merged.metadata_json["merged"] is True
    assert merged.salience == pytest.approx(0.75)


def test_arbitrator_interrupts_low_salience_thought() -> None:
    """High-salience incoming thoughts can interrupt weaker occupants."""
    working = WorkingMemoryManager(max_size=1)
    backlog = BacklogMemoryManager()
    arbitrator = AttentionArbitrator()
    working.set_thought(make_thought("weak", "background task", salience=0.2))

    incoming_salience = INTERRUPTION_SALIENCE_THRESHOLD + INTERRUPTION_MARGIN
    result = arbitrator.arbitrate(
        working,
        backlog,
        make_payload("urgent system alert", salience=incoming_salience),
        now=NOW,
        thought_id="urgent",
    )

    assert result.action == "interrupted"
    assert working.get("urgent") is not None
    assert backlog.get("weak") is not None


def test_arbitrator_replaces_without_interruption_when_below_threshold() -> None:
    """Full memory still evicts the weakest thought without interruption semantics."""
    working = WorkingMemoryManager(max_size=1)
    backlog = BacklogMemoryManager()
    arbitrator = AttentionArbitrator()
    working.set_thought(make_thought("weak", "background task", salience=0.4))

    result = arbitrator.arbitrate(
        working,
        backlog,
        make_payload("moderate priority item", salience=0.55),
        now=NOW,
        thought_id="moderate",
    )

    assert result.action == "replaced"
    assert working.get("moderate") is not None
    assert backlog.get("weak") is not None


def test_arbitrator_applies_conflict_penalties_before_competition() -> None:
    """Existing contradictory thoughts are penalized during arbitration."""
    working = WorkingMemoryManager(max_size=3)
    backlog = BacklogMemoryManager()
    arbitrator = AttentionArbitrator()
    working.set_thought(make_thought("a", "enable memory persistence", 0.8))
    working.set_thought(make_thought("b", "do not enable memory persistence", 0.8))

    arbitrator.arbitrate(
        working,
        backlog,
        make_payload("unrelated planning note", salience=0.3),
        now=NOW,
        thought_id="c",
    )

    assert working.get("a").salience == pytest.approx(0.65)
    assert working.get("b").salience == pytest.approx(0.65)
