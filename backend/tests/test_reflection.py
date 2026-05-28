"""Consolidation and reflection tests."""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.cognitive.reflection import ReflectionEngine
from app.config.settings import Settings
from app.memory.abstraction_repository import MemoryAbstractionRepository
from app.memory.consolidation import ConsolidationService
from app.memory.repository import ThoughtRepository
from app.models.schemas import ThoughtCreate
from app.services.database import get_session_factory, init_db


NOW = datetime(2026, 5, 28, 12, 0, 0)

RUST_CLUSTER_RESPONSE = {
    "summary": "User repeatedly returns to systems-level engineering interests",
    "theme": "systems engineering",
    "confidence": 0.86,
}


class FakeAbstractionProvider:
    """Deterministic LLM stub for abstraction generation."""

    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or RUST_CLUSTER_RESPONSE
        self.calls = 0

    async def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        """Return a fixed abstraction payload.

        Args:
            system_prompt: Captured system prompt.
            user_prompt: Captured user prompt.

        Returns:
            str: JSON abstraction payload.
        """
        self.calls += 1
        return json.dumps(self.payload)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Create an isolated SQLite database path."""
    path = tmp_path / "reflection.db"
    init_db(path)
    return path


@pytest.fixture
def db_session(db_path: Path) -> Session:
    """Provide an isolated SQLite session for each test."""
    session = get_session_factory(db_path)()
    yield session
    session.close()


def seed_rust_thoughts(repo: ThoughtRepository) -> None:
    """Persist sample thoughts that should consolidate together."""
    repo.add(
        ThoughtCreate(
            content="I want to learn Rust for systems programming",
            source="user_input",
            salience=0.7,
        ),
        now=NOW - timedelta(hours=2),
        thought_id="rust-1",
    )
    repo.add(
        ThoughtCreate(
            content="I watched systems programming videos",
            source="user_input",
            salience=0.65,
        ),
        now=NOW - timedelta(hours=1),
        thought_id="rust-2",
    )


def test_detect_theme_clusters_groups_related_thoughts(
    db_session: Session,
    db_path: Path,
) -> None:
    """Heuristic clustering groups lexically related recent thoughts."""
    thought_repo = ThoughtRepository(db_session)
    seed_rust_thoughts(thought_repo)
    service = ConsolidationService(
        get_session_factory(db_path),
        FakeAbstractionProvider(),
        settings=Settings(reflection_min_cluster_size=2),
    )

    recent = thought_repo.list_recent(since=NOW - timedelta(days=1))
    clusters = service.detect_theme_clusters(recent)

    assert len(clusters) == 1
    assert set(clusters[0].thought_ids) == {"rust-1", "rust-2"}
    assert "systems" in clusters[0].theme_hint
    assert "programming" in clusters[0].theme_hint


def test_consolidation_generates_and_stores_abstraction(
    db_session: Session,
    db_path: Path,
) -> None:
    """Consolidation uses the LLM once per cluster and stores semantic memory."""
    thought_repo = ThoughtRepository(db_session)
    abstraction_repo = MemoryAbstractionRepository(db_session)
    seed_rust_thoughts(thought_repo)
    provider = FakeAbstractionProvider()
    service = ConsolidationService(
        get_session_factory(db_path),
        provider,
        settings=Settings(reflection_min_cluster_size=2),
    )

    result = asyncio.run(service.consolidate(now=NOW))

    assert result.reviewed_thoughts == 2
    assert result.theme_clusters == 1
    assert len(result.created) == 1
    assert provider.calls == 1

    stored = abstraction_repo.list_all()
    assert len(stored) == 1
    assert stored[0].summary == RUST_CLUSTER_RESPONSE["summary"]
    assert set(stored[0].source_thought_ids) == {"rust-1", "rust-2"}

    assert thought_repo.get("rust-1").metadata_json["consolidated"] is True
    assert thought_repo.get("rust-2").metadata_json["consolidated"] is True


def test_consolidation_updates_existing_similar_abstraction(
    db_session: Session,
    db_path: Path,
) -> None:
    """Similar abstractions merge instead of duplicating long-term memory."""
    thought_repo = ThoughtRepository(db_session)
    abstraction_repo = MemoryAbstractionRepository(db_session)
    seed_rust_thoughts(thought_repo)
    provider = FakeAbstractionProvider()
    service = ConsolidationService(
        get_session_factory(db_path),
        provider,
        settings=Settings(reflection_min_cluster_size=2),
    )

    asyncio.run(service.consolidate(now=NOW))
    thought_repo.add(
        ThoughtCreate(
            content="Reading about systems programming design",
            source="user_input",
        ),
        now=NOW,
        thought_id="rust-3",
    )
    thought_repo.add(
        ThoughtCreate(
            content="Exploring systems programming patterns again",
            source="user_input",
        ),
        now=NOW,
        thought_id="rust-4",
    )

    second = asyncio.run(service.consolidate(now=NOW + timedelta(hours=1)))

    assert len(abstraction_repo.list_all()) == 1
    assert second.updated or second.created
    assert abstraction_repo.list_all()[0].support_count >= 2


def test_reflection_engine_runs_consolidation_cycle(
    db_session: Session,
    db_path: Path,
) -> None:
    """Reflection engine executes a consolidation pass."""
    thought_repo = ThoughtRepository(db_session)
    seed_rust_thoughts(thought_repo)
    service = ConsolidationService(
        get_session_factory(db_path),
        FakeAbstractionProvider(),
        settings=Settings(reflection_min_cluster_size=2),
    )
    engine = ReflectionEngine(service, interval_minutes=30.0, clock=lambda: NOW)

    result = asyncio.run(engine.reflect(now=NOW))

    assert engine.cycle_count == 1
    assert result.consolidation.created
