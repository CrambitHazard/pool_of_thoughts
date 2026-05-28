"""Spreading activation over associative thought graphs."""

from __future__ import annotations

from collections import deque

from app.memory.graph.protocol import GraphStore
from app.memory.graph.types import ActivationResult, GraphThemeCluster, ThoughtLink
from app.models.graph_types import RELATION_PROPAGATION, RelationType


class SpreadingActivationEngine:
    """Propagate activation through weighted edges with hop decay."""

    def __init__(
        self,
        store: GraphStore,
        hop_decay: float = 0.5,
        max_hops: int = 3,
    ) -> None:
        """Initialize the activation engine.

        Args:
            store: Graph backing store.
            hop_decay: Multiplier applied per graph hop.
            max_hops: Maximum propagation distance.
        """
        self.store = store
        self.hop_decay = hop_decay
        self.max_hops = max_hops

    def activate(self, source_id: str, strength: float = 1.0) -> ActivationResult:
        """Spread activation from a source thought.

        Args:
            source_id: Thought to activate.
            strength: Initial activation magnitude.

        Returns:
            ActivationResult: Activation levels keyed by thought id.
        """
        if not self.store.has_node(source_id):
            self.store.add_node(source_id)

        activations: dict[str, float] = {source_id: strength}
        queue: deque[tuple[str, float, int]] = deque([(source_id, strength, 0)])

        while queue:
            node_id, current_strength, depth = queue.popleft()
            if depth >= self.max_hops:
                continue

            for neighbor_id, edge, delta_strength in self._neighbors(node_id, current_strength, depth):
                if neighbor_id == source_id and node_id != source_id:
                    continue

                previous = activations.get(neighbor_id, 0.0)
                activations[neighbor_id] = previous + delta_strength
                if depth + 1 < self.max_hops:
                    queue.append((neighbor_id, abs(delta_strength), depth + 1))

        return ActivationResult(
            source_id=source_id,
            initial_strength=strength,
            activations=activations,
            max_hops=self.max_hops,
        )

    def _neighbors(
        self,
        node_id: str,
        current_strength: float,
        depth: int,
    ) -> list[tuple[str, ThoughtLink, float]]:
        """Return traversable neighbors for one activation step.

        Args:
            node_id: Active node id.
            current_strength: Strength arriving at the node.
            depth: Current hop count.

        Returns:
            list[tuple[str, ThoughtLink, float]]: Neighbor id, edge, and delta strength.
        """
        _ = depth
        neighbors: list[tuple[str, ThoughtLink, float]] = []

        for edge in self.store.get_out_edges(node_id):
            if self._allows_traversal(edge.relation, forward=True):
                delta = self._delta_strength(current_strength, edge)
                neighbors.append((edge.target_id, edge, delta))

        for edge in self.store.get_in_edges(node_id):
            if self._allows_traversal(edge.relation, forward=False):
                delta = self._delta_strength(current_strength, edge)
                neighbors.append((edge.source_id, edge, delta))

        return neighbors

    def _delta_strength(self, current_strength: float, edge: ThoughtLink) -> float:
        """Compute activation transferred across one edge.

        Args:
            current_strength: Strength at the source node.
            edge: Traversed edge.

        Returns:
            float: Signed activation delta.
        """
        propagation = RELATION_PROPAGATION[edge.relation]
        return current_strength * self.hop_decay * edge.weight * propagation

    @staticmethod
    def _allows_traversal(relation: RelationType, forward: bool) -> bool:
        """Return whether an edge may be traversed in a direction.

        Args:
            relation: Edge relation type.
            forward: True when traversing source to target.

        Returns:
            bool: True when traversal is allowed.
        """
        if relation in {RelationType.RELATED_TO, RelationType.CONTRADICTS, RelationType.REINFORCES}:
            return True
        if relation == RelationType.CAUSES:
            return forward
        if relation == RelationType.DERIVED_FROM:
            return not forward
        return True
