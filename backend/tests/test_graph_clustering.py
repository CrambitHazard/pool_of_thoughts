"""Theme clustering tests for associative graphs."""

from datetime import datetime

import pytest

from app.memory.graph import ThoughtGraph
from app.memory.graph.clustering import GraphClusteringService
from app.memory.repository import ThoughtRepository
from app.models.schemas import ThoughtCreate

NOW = datetime(2026, 5, 28, 12, 0, 0)


@pytest.fixture
def session_factory(db_path):
    """Provide a session factory bound to the test database."""
    from app.services.database import get_session_factory

    return get_session_factory(db_path)


@pytest.fixture
def db_path(tmp_path):
    """Provide an isolated SQLite database path."""
    from app.services.database import init_db

    path = tmp_path / "cluster.db"
    init_db(path)
    return path


@pytest.fixture
def thought_graph(session_factory):
    """Provide a ThoughtGraph for clustering integration tests."""
    return ThoughtGraph(session_factory)


def test_clustering_groups_recurring_themes() -> None:
    """Lexical overlap groups recurring thoughts into theme clusters."""
    service = GraphClusteringService()
    from app.models.schemas import ThoughtRead

    thoughts = [
        ThoughtRead(
            id="1",
            content="Laguna memory model draft",
            source="test",
            salience=0.5,
            emotional_weight=0.0,
            novelty=0.0,
            resolved=False,
            created_at=NOW,
            expires_at=None,
            times_resurfaced=0,
            last_accessed=NOW,
            metadata_json={},
        ),
        ThoughtRead(
            id="2",
            content="Laguna memory model outline",
            source="test",
            salience=0.5,
            emotional_weight=0.0,
            novelty=0.0,
            resolved=False,
            created_at=NOW,
            expires_at=None,
            times_resurfaced=0,
            last_accessed=NOW,
            metadata_json={},
        ),
        ThoughtRead(
            id="3",
            content="Unrelated cooking recipe",
            source="test",
            salience=0.5,
            emotional_weight=0.0,
            novelty=0.0,
            resolved=False,
            created_at=NOW,
            expires_at=None,
            times_resurfaced=0,
            last_accessed=NOW,
            metadata_json={},
        ),
    ]

    clusters = service.detect_clusters(thoughts)

    assert len(clusters) == 1
    assert set(clusters[0].thought_ids) == {"1", "2"}
    assert "laguna" in clusters[0].label


def test_thought_graph_persists_clusters_and_links(
    thought_graph: ThoughtGraph,
    session_factory,
) -> None:
    """Clustering persists records and creates intra-cluster related_to edges."""
    session = session_factory()
    try:
        repo = ThoughtRepository(session)
        repo.add(
            ThoughtCreate(content="Rust systems programming study", source="test"),
            now=NOW,
            thought_id="r1",
        )
        repo.add(
            ThoughtCreate(content="Rust systems programming practice", source="test"),
            now=NOW,
            thought_id="r2",
        )
    finally:
        session.close()

    clusters = thought_graph.cluster_recent_thoughts(persist=True, link_members=True, now=NOW)

    assert len(clusters) == 1
    assert len(clusters[0].thought_ids) == 2

    neighbors = thought_graph.neighbors("r1")
    assert any(edge.target_thought_id == "r2" for edge in neighbors)

    session = session_factory()
    try:
        from app.memory.graph_repository import ThoughtGraphRepository

        stored = ThoughtGraphRepository(session).list_clusters()
        assert len(stored) == 1
    finally:
        session.close()
