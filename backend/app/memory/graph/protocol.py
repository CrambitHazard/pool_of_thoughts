"""Graph store protocol for future backend migration."""

from __future__ import annotations

from typing import Protocol

from app.memory.graph.types import ThoughtLink
from app.models.graph_types import RelationType


class GraphStore(Protocol):
    """Minimal graph interface decoupled from NetworkX or a graph DB."""

    def add_node(self, node_id: str) -> None:
        """Ensure a node exists in the graph."""

    def has_node(self, node_id: str) -> bool:
        """Return whether a node is present."""

    def remove_node(self, node_id: str) -> None:
        """Remove a node and its incident edges."""

    def add_edge(self, link: ThoughtLink) -> None:
        """Insert or replace a directed edge."""

    def remove_edge(self, link_id: str) -> bool:
        """Remove an edge by identifier."""

    def get_edge(self, link_id: str) -> ThoughtLink | None:
        """Fetch a single edge."""

    def get_out_edges(self, node_id: str) -> list[ThoughtLink]:
        """Return edges leaving a node."""

    def get_in_edges(self, node_id: str) -> list[ThoughtLink]:
        """Return edges entering a node."""

    def edges(self) -> list[ThoughtLink]:
        """Return all edges in the graph."""

    def nodes(self) -> list[str]:
        """Return all node identifiers."""

    def clear(self) -> None:
        """Remove all nodes and edges."""
