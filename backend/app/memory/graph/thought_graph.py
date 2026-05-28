"""ThoughtGraph facade for associative cognition."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from app.cognitive.similarity import ThoughtSimilarity
from app.memory.graph.activation import SpreadingActivationEngine
from app.memory.graph.clustering import ClusteringConfig, GraphClusteringService
from app.memory.graph.networkx_store import NetworkXGraphStore
from app.memory.graph.types import ActivationResult, GraphThemeCluster, ThoughtLink
from app.models.graph_types import RelationType
from app.memory.graph_repository import ThoughtGraphRepository
from app.memory.repository import ThoughtRepository
from app.models.schemas import ThoughtLinkCreate, ThoughtLinkRead, ThoughtClusterRead, ThoughtRead


class ThoughtGraph:
    """Associative cognition graph with persistence and spreading activation."""

    AUTO_LINK_THRESHOLD = 0.45

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        store: NetworkXGraphStore | None = None,
        similarity: ThoughtSimilarity | None = None,
        hop_decay: float = 0.5,
        max_hops: int = 3,
        clustering_config: ClusteringConfig | None = None,
    ) -> None:
        """Initialize the thought graph.

        Args:
            session_factory: Database session factory.
            store: Optional in-memory graph store override.
            similarity: Lexical similarity helper for auto-linking.
            hop_decay: Activation decay per hop.
            max_hops: Maximum activation propagation distance.
            clustering_config: Theme clustering thresholds.
        """
        self.session_factory = session_factory
        self.store = store or NetworkXGraphStore()
        self.similarity = similarity or ThoughtSimilarity()
        self.activation_engine = SpreadingActivationEngine(
            self.store,
            hop_decay=hop_decay,
            max_hops=max_hops,
        )
        self.clustering = GraphClusteringService(self.similarity, clustering_config)
        self._loaded = False

    def ensure_loaded(self) -> None:
        """Load persisted edges into the in-memory graph store.

        Returns:
            None
        """
        if self._loaded:
            return

        session = self.session_factory()
        try:
            repository = ThoughtGraphRepository(session)
            for link in repository.load_links():
                self.store.add_edge(link)
                self.store.add_node(link.source_id)
                self.store.add_node(link.target_id)
        finally:
            session.close()

        self._loaded = True

    def link(
        self,
        source_id: str,
        target_id: str,
        relation: RelationType,
        weight: float = 0.5,
        metadata_json: dict | None = None,
        now: datetime | None = None,
    ) -> ThoughtLinkRead:
        """Create or update a weighted association between thoughts.

        Args:
            source_id: Source thought id.
            target_id: Target thought id.
            relation: Relationship type.
            weight: Edge weight between 0.0 and 1.0.
            metadata_json: Optional edge metadata.
            now: Persistence timestamp.

        Returns:
            ThoughtLinkRead: Persisted edge record.
        """
        self.ensure_loaded()
        payload = ThoughtLinkCreate(
            source_thought_id=source_id,
            target_thought_id=target_id,
            relation=relation,
            weight=weight,
            metadata_json=metadata_json or {},
        )

        session = self.session_factory()
        try:
            repository = ThoughtGraphRepository(session)
            stored = repository.add_edge(payload, now=now)
        finally:
            session.close()

        link = ThoughtLink(
            id=stored.id,
            source_id=stored.source_thought_id,
            target_id=stored.target_thought_id,
            relation=RelationType(stored.relation_type),
            weight=stored.weight,
            metadata_json=dict(stored.metadata_json),
        )
        self.store.add_edge(link)
        return stored

    def unlink(self, link_id: str) -> bool:
        """Remove an edge from memory and SQLite.

        Args:
            link_id: Edge primary key.

        Returns:
            bool: True when the edge was removed.
        """
        self.ensure_loaded()
        removed = self.store.remove_edge(link_id)

        session = self.session_factory()
        try:
            repository = ThoughtGraphRepository(session)
            persisted_removed = repository.delete_edge(link_id)
        finally:
            session.close()

        return removed or persisted_removed

    def neighbors(self, thought_id: str) -> list[ThoughtLinkRead]:
        """Return all edges incident to a thought.

        Args:
            thought_id: Thought identifier.

        Returns:
            list[ThoughtLinkRead]: Incoming and outgoing edges.
        """
        self.ensure_loaded()
        session = self.session_factory()
        try:
            repository = ThoughtGraphRepository(session)
            edges = repository.list_edges()
            return [
                edge
                for edge in edges
                if edge.source_thought_id == thought_id or edge.target_thought_id == thought_id
            ]
        finally:
            session.close()

    def activate(self, thought_id: str, strength: float = 1.0) -> ActivationResult:
        """Spread activation from a source thought through the graph.

        Args:
            thought_id: Thought to activate.
            strength: Initial activation magnitude.

        Returns:
            ActivationResult: Activation levels keyed by thought id.
        """
        self.ensure_loaded()
        return self.activation_engine.activate(thought_id, strength=strength)

    def apply_activation_to_salience(
        self,
        activation: ActivationResult,
        thoughts: list[ThoughtRead],
        boost_factor: float = 0.1,
    ) -> list[ThoughtRead]:
        """Boost salience for thoughts reached by spreading activation.

        Args:
            activation: Activation output.
            thoughts: Mutable thought list to adjust.
            boost_factor: Salience increment per unit activation.

        Returns:
            list[ThoughtRead]: Thoughts with adjusted salience values.
        """
        updated: list[ThoughtRead] = []
        for thought in thoughts:
            delta = activation.activations.get(thought.id, 0.0)
            if delta <= 0:
                updated.append(thought)
                continue

            boosted = thought.model_copy(
                update={"salience": min(1.0, thought.salience + delta * boost_factor)},
            )
            updated.append(boosted)
        return updated

    def auto_link_thought(
        self,
        thought: ThoughtRead,
        candidates: list[ThoughtRead],
        now: datetime | None = None,
    ) -> list[ThoughtLinkRead]:
        """Create related_to edges to lexically similar thoughts.

        Args:
            thought: New or active thought.
            candidates: Existing thoughts to compare against.
            now: Persistence timestamp.

        Returns:
            list[ThoughtLinkRead]: Created or updated edge records.
        """
        self.ensure_loaded()
        created: list[ThoughtLinkRead] = []

        for candidate in candidates:
            if candidate.id == thought.id:
                continue

            score = self.similarity.score_thoughts(thought, candidate)
            if score < self.AUTO_LINK_THRESHOLD:
                continue

            created.append(
                self.link(
                    thought.id,
                    candidate.id,
                    RelationType.RELATED_TO,
                    weight=round(score, 4),
                    metadata_json={"auto_linked": True, "similarity": round(score, 4)},
                    now=now,
                )
            )

        return created

    def cluster_recent_thoughts(
        self,
        since: datetime | None = None,
        limit: int = 100,
        persist: bool = True,
        link_members: bool = True,
        now: datetime | None = None,
    ) -> list[ThoughtClusterRead]:
        """Detect recurring themes and optionally persist clusters and links.

        Args:
            since: Optional lower bound for thought created_at.
            limit: Maximum thoughts to analyze.
            persist: Store cluster records in SQLite.
            link_members: Create related_to edges inside each cluster.
            now: Reference timestamp.

        Returns:
            list[ThoughtClusterRead]: Detected theme clusters.
        """
        self.ensure_loaded()
        current_time = now or datetime.now()

        session = self.session_factory()
        try:
            thought_repo = ThoughtRepository(session)
            graph_repo = ThoughtGraphRepository(session)
            query_since = since
            recent = thought_repo.list_recent(
                since=query_since,
                limit=limit,
                exclude_consolidated=False,
            )
            detected = self.clustering.detect_clusters(recent)
            stored: list[ThoughtClusterRead] = []

            for cluster in detected:
                if link_members:
                    for source_id, target_id, relation, weight in self.clustering.suggested_links(cluster):
                        self.link(
                            source_id,
                            target_id,
                            relation,
                            weight=weight,
                            metadata_json={"cluster_id": cluster.id},
                            now=current_time,
                        )

                if persist:
                    stored.append(graph_repo.save_cluster(cluster, now=current_time))
                else:
                    stored.append(
                        ThoughtClusterRead(
                            id=cluster.id,
                            label=cluster.label,
                            thought_ids=list(cluster.thought_ids),
                            cohesion=cluster.cohesion,
                            created_at=current_time,
                            updated_at=current_time,
                            metadata_json=dict(cluster.metadata_json),
                        )
                    )

            return stored
        finally:
            session.close()

    def stats(self) -> dict[str, int]:
        """Return basic graph statistics.

        Returns:
            dict[str, int]: Node and edge counts.
        """
        self.ensure_loaded()
        return {
            "nodes": len(self.store.nodes()),
            "edges": len(self.store.edges()),
        }
