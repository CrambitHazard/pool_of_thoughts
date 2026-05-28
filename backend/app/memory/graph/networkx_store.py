"""NetworkX-backed graph store implementation."""

from __future__ import annotations

import networkx as nx

from app.memory.graph.protocol import GraphStore
from app.memory.graph.types import ThoughtLink


class NetworkXGraphStore:
    """In-memory directed graph using NetworkX."""

    def __init__(self) -> None:
        """Initialize an empty directed graph."""
        self._graph = nx.MultiDiGraph()

    def add_node(self, node_id: str) -> None:
        """Ensure a node exists in the graph.

        Args:
            node_id: Thought identifier.

        Returns:
            None
        """
        self._graph.add_node(node_id)

    def has_node(self, node_id: str) -> bool:
        """Return whether a node is present.

        Args:
            node_id: Thought identifier.

        Returns:
            bool: True when the node exists.
        """
        return self._graph.has_node(node_id)

    def remove_node(self, node_id: str) -> None:
        """Remove a node and its incident edges.

        Args:
            node_id: Thought identifier.

        Returns:
            None
        """
        if self._graph.has_node(node_id):
            self._graph.remove_node(node_id)

    def add_edge(self, link: ThoughtLink) -> None:
        """Insert or replace a directed edge.

        Args:
            link: Edge payload.

        Returns:
            None
        """
        self.add_node(link.source_id)
        self.add_node(link.target_id)
        if self._graph.has_edge(link.source_id, link.target_id, key=link.id):
            self._graph.remove_edge(link.source_id, link.target_id, key=link.id)
        self._graph.add_edge(
            link.source_id,
            link.target_id,
            key=link.id,
            link_id=link.id,
            relation=str(link.relation),
            weight=link.weight,
            metadata_json=dict(link.metadata_json),
        )

    def remove_edge(self, link_id: str) -> bool:
        """Remove an edge by identifier.

        Args:
            link_id: Edge primary key.

        Returns:
            bool: True when an edge was removed.
        """
        for source, target, key, data in list(self._graph.edges(keys=True, data=True)):
            if data.get("link_id") == link_id:
                self._graph.remove_edge(source, target, key)
                return True
        return False

    def get_edge(self, link_id: str) -> ThoughtLink | None:
        """Fetch a single edge.

        Args:
            link_id: Edge primary key.

        Returns:
            ThoughtLink | None: Stored edge when found.
        """
        for source, target, _key, data in self._graph.edges(keys=True, data=True):
            if data.get("link_id") == link_id:
                return _edge_to_link(source, target, data)
        return None

    def get_out_edges(self, node_id: str) -> list[ThoughtLink]:
        """Return edges leaving a node.

        Args:
            node_id: Thought identifier.

        Returns:
            list[ThoughtLink]: Outgoing edges.
        """
        if not self._graph.has_node(node_id):
            return []

        links: list[ThoughtLink] = []
        for _source, target, _key, data in self._graph.out_edges(node_id, keys=True, data=True):
            links.append(_edge_to_link(node_id, target, data))
        return links

    def get_in_edges(self, node_id: str) -> list[ThoughtLink]:
        """Return edges entering a node.

        Args:
            node_id: Thought identifier.

        Returns:
            list[ThoughtLink]: Incoming edges.
        """
        if not self._graph.has_node(node_id):
            return []

        links: list[ThoughtLink] = []
        for source, _target, _key, data in self._graph.in_edges(node_id, keys=True, data=True):
            links.append(_edge_to_link(source, node_id, data))
        return links

    def edges(self) -> list[ThoughtLink]:
        """Return all edges in the graph.

        Returns:
            list[ThoughtLink]: Stored edges.
        """
        links: list[ThoughtLink] = []
        for source, target, _key, data in self._graph.edges(keys=True, data=True):
            links.append(_edge_to_link(source, target, data))
        return links

    def nodes(self) -> list[str]:
        """Return all node identifiers.

        Returns:
            list[str]: Node ids sorted for deterministic iteration.
        """
        return sorted(self._graph.nodes())

    def clear(self) -> None:
        """Remove all nodes and edges.

        Returns:
            None
        """
        self._graph.clear()


def _edge_to_link(source: str, target: str, data: dict) -> ThoughtLink:
    """Convert NetworkX edge data into a ThoughtLink.

    Args:
        source: Edge source node id.
        target: Edge target node id.
        data: Edge attribute payload.

    Returns:
        ThoughtLink: Normalized edge object.
    """
    from app.models.graph_types import RelationType

    return ThoughtLink(
        id=str(data["link_id"]),
        source_id=source,
        target_id=target,
        relation=RelationType(str(data["relation"])),
        weight=float(data["weight"]),
        metadata_json=dict(data.get("metadata_json", {})),
    )
