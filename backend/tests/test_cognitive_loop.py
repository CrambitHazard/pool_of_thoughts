"""Cognitive loop tests."""

import asyncio
from datetime import datetime, timedelta

import pytest

from app.cognitive.loop import CognitiveLoop
from app.cognitive.resurfacing import ResurfacingStrategy
from app.memory.backlog import BacklogMemoryManager
from app.memory.working_memory import WORKING_MEMORY_MAX_SIZE, WorkingMemoryManager
from app.models.schemas import ThoughtCreate, ThoughtRead


NOW = datetime(2026, 5, 28, 12, 0, 0)


def make_thought(
    thought_id: str,
    content: str,
    *,
    salience: float = 0.5,
    novelty: float = 0.0,
    emotional_weight: float = 0.0,
    times_resurfaced: int = 0,
    expires_at: datetime | None = None,
    resolved: bool = False,
) -> ThoughtRead:
    """Build a thought object for loop tests."""
    return ThoughtRead(
        id=thought_id,
        content=content,
        source="test",
        salience=salience,
        emotional_weight=emotional_weight,
        novelty=novelty,
        resolved=resolved,
        created_at=NOW,
        expires_at=expires_at,
        times_resurfaced=times_resurfaced,
        last_accessed=NOW,
        metadata_json={},
    )


def make_loop(
    max_size: int = WORKING_MEMORY_MAX_SIZE,
) -> CognitiveLoop:
    """Create a cognitive loop with fresh memory stores."""
    return CognitiveLoop(
        working_memory=WorkingMemoryManager(max_size=max_size),
        backlog=BacklogMemoryManager(),
        strategy=ResurfacingStrategy(),
        interval_minutes=1.0,
        clock=lambda: NOW,
    )


def test_ingest_routes_evicted_thought_to_backlog() -> None:
    """Evicted working-memory thoughts are queued in backlog."""
    loop = make_loop(max_size=2)
    loop.ingest_thought(
        ThoughtCreate(content="one", source="test", salience=0.1),
        now=NOW,
        thought_id="one",
    )
    loop.ingest_thought(
        ThoughtCreate(content="two", source="test", salience=0.9),
        now=NOW,
        thought_id="two",
    )
    loop.ingest_thought(
        ThoughtCreate(content="three", source="test", salience=0.95),
        now=NOW,
        thought_id="three",
    )

    assert loop.backlog.get("one") is not None
    assert loop.working_memory.get("three") is not None
    assert loop.working_memory.size() == 2


def test_tick_decays_salience_in_working_and_backlog() -> None:
    """Each tick applies salience decay to both memory tiers."""
    loop = make_loop(max_size=3)
    loop.ingest_thought(
        ThoughtCreate(content="active", source="test", salience=1.0),
        now=NOW,
        thought_id="active",
    )
    loop.backlog.enqueue(make_thought("backlog-1", "waiting", salience=1.0, novelty=0.1))

    later = NOW + timedelta(hours=2)
    loop.tick(now=later)

    active = loop.working_memory.get_active_thoughts(now=later)[0]
    backlog = loop.backlog.get("backlog-1")

    assert active.salience == pytest.approx(0.9)
    assert backlog is not None
    assert backlog.salience == pytest.approx(0.9)


def test_tick_removes_expired_thoughts() -> None:
    """Expired thoughts are removed from working memory and backlog."""
    loop = make_loop(max_size=3)
    loop.ingest_thought(
        ThoughtCreate(
            content="short-lived",
            source="test",
            expires_at=NOW + timedelta(minutes=30),
        ),
        now=NOW,
        thought_id="working-expired",
    )
    loop.backlog.enqueue(
        make_thought(
            "backlog-expired",
            "old backlog",
            expires_at=NOW + timedelta(minutes=15),
        )
    )

    result = loop.tick(now=NOW + timedelta(hours=1))

    assert result.expired_removed == 2
    assert loop.backlog.get("backlog-expired") is None
    assert loop.working_memory.size() == 0


def test_tick_resurfaces_high_novelty_thought() -> None:
    """High-novelty backlog thoughts re-enter working memory."""
    loop = make_loop(max_size=2)
    loop.ingest_thought(
        ThoughtCreate(content="a", source="test", salience=0.9),
        now=NOW,
        thought_id="a",
    )
    loop.ingest_thought(
        ThoughtCreate(content="b", source="test", salience=0.8),
        now=NOW,
        thought_id="b",
    )
    loop.backlog.enqueue(
        make_thought("novel", "important insight", salience=0.3, novelty=0.9)
    )

    result = loop.tick(now=NOW)

    assert result.resurfaced == ["novel"]
    restored = loop.working_memory.get("novel")
    assert restored is not None
    assert restored.times_resurfaced == 1


def test_tick_resurfaces_repeated_relevance_thought() -> None:
    """Previously resurfaced thoughts with salience can return."""
    loop = make_loop(max_size=2)
    loop.ingest_thought(
        ThoughtCreate(content="a", source="test", salience=0.9),
        now=NOW,
        thought_id="a",
    )
    loop.ingest_thought(
        ThoughtCreate(content="b", source="test", salience=0.8),
        now=NOW,
        thought_id="b",
    )
    loop.backlog.enqueue(
        make_thought(
            "repeat",
            "recurring task",
            salience=0.4,
            novelty=0.1,
            times_resurfaced=1,
        )
    )

    result = loop.tick(now=NOW)

    assert result.resurfaced == ["repeat"]
    assert loop.working_memory.get("repeat") is not None


def test_resurfacing_evicts_lowest_salience_back_to_backlog() -> None:
    """Resurfacing into full working memory pushes the weakest thought to backlog."""
    loop = make_loop(max_size=2)
    loop.ingest_thought(
        ThoughtCreate(content="strong", source="test", salience=0.9),
        now=NOW,
        thought_id="strong",
    )
    loop.ingest_thought(
        ThoughtCreate(content="weak", source="test", salience=0.2),
        now=NOW,
        thought_id="weak",
    )
    loop.backlog.enqueue(
        make_thought("novel", "return me", salience=0.5, novelty=0.95)
    )

    result = loop.tick(now=NOW)

    assert result.resurfaced == ["novel"]
    assert result.evicted_to_backlog == ["weak"]
    assert loop.backlog.get("weak") is not None
    assert loop.working_memory.get("novel") is not None


def test_background_scheduler_runs_ticks() -> None:
    """Background loop executes at least one tick before stopping."""

    async def run() -> None:
        loop = CognitiveLoop(
            working_memory=WorkingMemoryManager(max_size=3),
            backlog=BacklogMemoryManager(),
            interval_minutes=0.01,
        )
        loop.start()
        await asyncio.sleep(0.05)
        await loop.stop()
        assert loop.tick_count >= 1

    asyncio.run(run())
