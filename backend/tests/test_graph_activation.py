"""Spreading activation tests."""

from datetime import datetime

import pytest

from app.memory.graph import ThoughtGraph
from app.models.graph_types import RelationType

NOW = datetime(2026, 5, 28, 12, 0, 0)


@pytest.fixture
def thought_graph(session_factory):
    """Provide a ThoughtGraph with short hop settings."""
    return ThoughtGraph(session_factory, hop_decay=0.5, max_hops=3)


@pytest.fixture
def session_factory(db_path):
    """Provide a session factory bound to the test database."""
    from app.services.database import get_session_factory

    return get_session_factory(db_path)


@pytest.fixture
def db_path(tmp_path):
    """Provide an isolated SQLite database path."""
    from app.services.database import init_db

    path = tmp_path / "activation.db"
    init_db(path)
    return path


def test_spreading_activation_decays_with_distance(thought_graph: ThoughtGraph) -> None:
    """Activation weakens as graph distance increases."""
    thought_graph.link("a", "b", RelationType.RELATED_TO, weight=1.0, now=NOW)
    thought_graph.link("b", "c", RelationType.RELATED_TO, weight=1.0, now=NOW)

    result = thought_graph.activate("a", strength=1.0)

    assert result.activations["a"] == pytest.approx(1.0)
    assert result.activations["b"] > result.activations["c"]
    assert result.activations["c"] > 0.0


def test_reinforces_propagates_stronger_than_related(thought_graph: ThoughtGraph) -> None:
    """Reinforces edges transfer more activation than plain related_to edges."""
    thought_graph.link("source", "reinforced", RelationType.REINFORCES, weight=1.0, now=NOW)
    thought_graph.link("source", "related", RelationType.RELATED_TO, weight=1.0, now=NOW)

    result = thought_graph.activate("source", strength=1.0)

    assert result.activations["reinforced"] > result.activations["related"]


def test_contradicts_reduces_neighbor_activation(thought_graph: ThoughtGraph) -> None:
    """Contradiction edges apply negative propagation."""
    thought_graph.link("anchor", "conflict", RelationType.CONTRADICTS, weight=1.0, now=NOW)

    result = thought_graph.activate("anchor", strength=1.0)

    assert result.activations["conflict"] < 0.0


def test_causes_is_directional(thought_graph: ThoughtGraph) -> None:
    """Causes edges propagate forward but not backward."""
    thought_graph.link("cause", "effect", RelationType.CAUSES, weight=1.0, now=NOW)

    forward = thought_graph.activate("cause", strength=1.0)
    backward = thought_graph.activate("effect", strength=1.0)

    assert forward.activations.get("effect", 0.0) > 0.0
    assert backward.activations.get("cause", 0.0) == 0.0


def test_derived_from_propagates_to_source(thought_graph: ThoughtGraph) -> None:
    """Derived_from edges propagate from derivative back to source."""
    thought_graph.link("origin", "derivative", RelationType.DERIVED_FROM, weight=1.0, now=NOW)

    result = thought_graph.activate("derivative", strength=1.0)

    assert result.activations.get("origin", 0.0) > 0.0
