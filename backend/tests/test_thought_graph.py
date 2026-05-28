"""ThoughtGraph persistence and linking tests."""

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.memory.graph import ThoughtGraph
from app.models.graph_types import RelationType
from app.memory.graph_repository import ThoughtGraphRepository
from app.memory.repository import ThoughtRepository
from app.models.schemas import ThoughtCreate, ThoughtLinkCreate
from app.services.database import get_session_factory, init_db

NOW = datetime(2026, 5, 28, 12, 0, 0)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Provide an isolated SQLite database path."""
    path = tmp_path / "graph.db"
    init_db(path)
    return path


@pytest.fixture
def session_factory(db_path: Path):
    """Provide a session factory bound to the test database."""
    return get_session_factory(db_path)


@pytest.fixture
def db_session(session_factory) -> Session:
    """Provide an isolated SQLite session for each test."""
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def thought_graph(session_factory):
    """Provide a ThoughtGraph backed by the test database."""
    return ThoughtGraph(session_factory, hop_decay=0.5, max_hops=2)


def test_graph_repository_persists_weighted_edge(db_session: Session) -> None:
    """Graph repository stores directed weighted edges."""
    repository = ThoughtGraphRepository(db_session)
    created = repository.add_edge(
        ThoughtLinkCreate(
            source_thought_id="a",
            target_thought_id="b",
            relation=RelationType.REINFORCES,
            weight=0.8,
        ),
        now=NOW,
        link_id="edge-1",
    )

    loaded = repository.get_edge("edge-1")

    assert created.relation_type == "reinforces"
    assert loaded is not None
    assert loaded.weight == 0.8


def test_thought_graph_links_all_relation_types(thought_graph: ThoughtGraph) -> None:
    """ThoughtGraph supports the required relationship vocabulary."""
    relations = [
        RelationType.RELATED_TO,
        RelationType.CONTRADICTS,
        RelationType.CAUSES,
        RelationType.REINFORCES,
        RelationType.DERIVED_FROM,
    ]

    for index, relation in enumerate(relations):
        source = f"source-{index}"
        target = f"target-{index}"
        stored = thought_graph.link(source, target, relation, weight=0.6, now=NOW)
        assert stored.relation_type == str(relation)

    stats = thought_graph.stats()
    assert stats["edges"] == len(relations)
    assert stats["nodes"] == len(relations) * 2


def test_thought_graph_reloads_from_sqlite(session_factory, thought_graph: ThoughtGraph) -> None:
    """Persisted edges reload into a fresh in-memory graph store."""
    thought_graph.link("alpha", "beta", RelationType.RELATED_TO, weight=0.7, now=NOW)

    reloaded = ThoughtGraph(session_factory)
    reloaded.ensure_loaded()

    neighbors = reloaded.neighbors("alpha")
    assert len(neighbors) == 1
    assert neighbors[0].target_thought_id == "beta"


def test_auto_link_creates_related_to_edges(
    session_factory,
    thought_graph: ThoughtGraph,
    db_session: Session,
) -> None:
    """Similar thoughts receive automatic related_to edges."""
    repo = ThoughtRepository(db_session)
    first = repo.add(
        ThoughtCreate(content="Finish Laguna memory model draft", source="test"),
        now=NOW,
        thought_id="t1",
    )
    second = repo.add(
        ThoughtCreate(content="Finish Laguna memory model outline", source="test"),
        now=NOW,
        thought_id="t2",
    )

    created = thought_graph.auto_link_thought(second, [first], now=NOW)

    assert len(created) == 1
    assert created[0].relation_type == "related_to"
    assert created[0].weight >= thought_graph.AUTO_LINK_THRESHOLD
