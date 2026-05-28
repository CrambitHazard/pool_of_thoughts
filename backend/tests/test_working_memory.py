"""Working memory manager tests."""

from datetime import datetime, timedelta

import pytest

from app.memory.working_memory import (
    SALIENCE_DECAY_PER_HOUR,
    WORKING_MEMORY_MAX_SIZE,
    WorkingMemoryManager,
)
from app.models.schemas import ThoughtCreate


NOW = datetime(2026, 5, 28, 12, 0, 0)


def make_payload(content: str, salience: float = 0.5) -> ThoughtCreate:
    """Build a thought payload for tests."""
    return ThoughtCreate(content=content, source="test", salience=salience)


def test_add_and_get_active_thoughts() -> None:
    """Added thoughts appear as active entries sorted by salience."""
    memory = WorkingMemoryManager()
    memory.add_thought(make_payload("alpha", 0.9), now=NOW, thought_id="a")
    memory.add_thought(make_payload("beta", 0.4), now=NOW, thought_id="b")

    active = memory.get_active_thoughts(now=NOW)

    assert [thought.id for thought in active] == ["a", "b"]
    assert active[0].content == "alpha"


def test_working_memory_capacity_evicts_lowest_salience() -> None:
    """Adding beyond capacity removes the lowest-salience thought."""
    memory = WorkingMemoryManager(max_size=WORKING_MEMORY_MAX_SIZE)

    for index in range(WORKING_MEMORY_MAX_SIZE):
        memory.add_thought(
            make_payload(f"thought-{index}", salience=0.1 * (index + 1)),
            now=NOW,
            thought_id=str(index),
        )

    memory.add_thought(make_payload("new-thought", salience=0.95), now=NOW, thought_id="new")

    active_ids = {thought.id for thought in memory.get_active_thoughts(now=NOW)}
    assert "0" not in active_ids
    assert "new" in active_ids
    assert memory.size() == WORKING_MEMORY_MAX_SIZE


def test_remove_thought() -> None:
    """Removing a thought drops it from active results."""
    memory = WorkingMemoryManager()
    memory.add_thought(make_payload("temporary"), now=NOW, thought_id="temp")

    assert memory.remove_thought("temp") is True
    assert memory.remove_thought("temp") is False
    assert memory.get_active_thoughts(now=NOW) == []


def test_update_salience() -> None:
    """Salience updates are reflected in active thought ordering."""
    memory = WorkingMemoryManager()
    memory.add_thought(make_payload("low", 0.2), now=NOW, thought_id="low")
    memory.add_thought(make_payload("high", 0.8), now=NOW, thought_id="high")

    updated = memory.update_salience("low", 0.95, now=NOW)

    assert updated is not None
    assert updated.salience == 0.95
    assert memory.get_active_thoughts(now=NOW)[0].id == "low"


def test_decay_salience_is_deterministic() -> None:
    """Salience decays linearly with elapsed hours since last access."""
    memory = WorkingMemoryManager()
    memory.add_thought(make_payload("fading", 1.0), now=NOW, thought_id="fade")

    later = NOW + timedelta(hours=2)
    memory.decay_salience(now=later)

    active = memory.get_active_thoughts(now=later)
    expected = 1.0 - (SALIENCE_DECAY_PER_HOUR * 2)

    assert len(active) == 1
    assert active[0].salience == pytest.approx(expected)


def test_expired_and_resolved_thoughts_are_not_active() -> None:
    """Expired or resolved thoughts are excluded from active results."""
    memory = WorkingMemoryManager()
    memory.add_thought(
        ThoughtCreate(
            content="expired",
            source="test",
            salience=0.8,
            expires_at=NOW + timedelta(minutes=30),
        ),
        now=NOW,
        thought_id="expired",
    )
    memory.add_thought(
        ThoughtCreate(content="resolved", source="test", salience=0.8, resolved=True),
        now=NOW,
        thought_id="resolved",
    )

    active_ids = {thought.id for thought in memory.get_active_thoughts(now=NOW + timedelta(hours=1))}
    assert active_ids == set()
