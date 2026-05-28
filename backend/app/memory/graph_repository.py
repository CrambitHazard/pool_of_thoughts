"""Persistence helpers for associative thought graphs."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime

from sqlalchemy.orm import Session

from app.memory.graph.types import GraphThemeCluster, ThoughtLink
from app.models.graph_types import RelationType
from app.models.schemas import ThoughtLinkCreate, ThoughtLinkRead, ThoughtClusterRead
from app.models.thought_cluster import ThoughtCluster
from app.models.thought_edge import ThoughtEdge


class ThoughtGraphRepository:
    """SQLite persistence for graph edges and theme clusters."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to a database session.

        Args:
            session: Active SQLAlchemy session.
        """
        self.session = session

    def list_edges(self) -> list[ThoughtLinkRead]:
        """Return all persisted graph edges.

        Returns:
            list[ThoughtLinkRead]: Stored edges ordered by creation time.
        """
        rows = (
            self.session.query(ThoughtEdge)
            .order_by(ThoughtEdge.created_at.asc(), ThoughtEdge.id.asc())
            .all()
        )
        return [ThoughtLinkRead.model_validate(row) for row in rows]

    def get_edge(self, link_id: str) -> ThoughtLinkRead | None:
        """Fetch one edge by identifier.

        Args:
            link_id: Edge primary key.

        Returns:
            ThoughtLinkRead | None: Stored edge when found.
        """
        row = self.session.get(ThoughtEdge, link_id)
        if row is None:
            return None
        return ThoughtLinkRead.model_validate(row)

    def add_edge(
        self,
        payload: ThoughtLinkCreate,
        now: datetime | None = None,
        link_id: str | None = None,
    ) -> ThoughtLinkRead:
        """Persist a new graph edge.

        Args:
            payload: Edge creation payload.
            now: Timestamp for created_at and updated_at.
            link_id: Optional deterministic identifier for tests.

        Returns:
            ThoughtLinkRead: Persisted edge.
        """
        current_time = now or datetime.now()
        existing = self._find_existing(payload)
        if existing is not None:
            return self.update_edge(
                existing.id,
                payload,
                now=current_time,
            )

        row = ThoughtEdge(
            id=link_id or str(uuid.uuid4()),
            source_thought_id=payload.source_thought_id,
            target_thought_id=payload.target_thought_id,
            relation_type=str(payload.relation),
            weight=payload.weight,
            created_at=current_time,
            updated_at=current_time,
            metadata_json=deepcopy(payload.metadata_json),
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return ThoughtLinkRead.model_validate(row)

    def update_edge(
        self,
        link_id: str,
        payload: ThoughtLinkCreate,
        now: datetime | None = None,
    ) -> ThoughtLinkRead:
        """Update an existing edge or upsert by relation tuple.

        Args:
            link_id: Edge primary key.
            payload: Updated edge values.
            now: Timestamp for updated_at.

        Returns:
            ThoughtLinkRead: Updated edge.
        """
        current_time = now or datetime.now()
        row = self.session.get(ThoughtEdge, link_id)
        if row is None:
            return self.add_edge(payload, now=current_time, link_id=link_id)

        row.source_thought_id = payload.source_thought_id
        row.target_thought_id = payload.target_thought_id
        row.relation_type = str(payload.relation)
        row.weight = payload.weight
        row.updated_at = current_time
        row.metadata_json = deepcopy(payload.metadata_json)
        self.session.commit()
        self.session.refresh(row)
        return ThoughtLinkRead.model_validate(row)

    def delete_edge(self, link_id: str) -> bool:
        """Delete a graph edge.

        Args:
            link_id: Edge primary key.

        Returns:
            bool: True when a record was deleted.
        """
        row = self.session.get(ThoughtEdge, link_id)
        if row is None:
            return False

        self.session.delete(row)
        self.session.commit()
        return True

    def list_clusters(self) -> list[ThoughtClusterRead]:
        """Return all persisted theme clusters.

        Returns:
            list[ThoughtClusterRead]: Stored clusters ordered by recency.
        """
        rows = (
            self.session.query(ThoughtCluster)
            .order_by(ThoughtCluster.updated_at.desc(), ThoughtCluster.id.asc())
            .all()
        )
        return [ThoughtClusterRead.model_validate(row) for row in rows]

    def save_cluster(
        self,
        cluster: GraphThemeCluster,
        now: datetime | None = None,
    ) -> ThoughtClusterRead:
        """Persist a detected theme cluster.

        Args:
            cluster: Cluster payload.
            now: Timestamp for persistence.

        Returns:
            ThoughtClusterRead: Stored cluster record.
        """
        current_time = now or datetime.now()
        row = ThoughtCluster(
            id=cluster.id,
            label=cluster.label,
            thought_ids=list(cluster.thought_ids),
            cohesion=cluster.cohesion,
            created_at=current_time,
            updated_at=current_time,
            metadata_json=deepcopy(cluster.metadata_json),
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return ThoughtClusterRead.model_validate(row)

    def delete_cluster(self, cluster_id: str) -> bool:
        """Delete a theme cluster record.

        Args:
            cluster_id: Cluster primary key.

        Returns:
            bool: True when a record was deleted.
        """
        row = self.session.get(ThoughtCluster, cluster_id)
        if row is None:
            return False

        self.session.delete(row)
        self.session.commit()
        return True

    def load_links(self) -> list[ThoughtLink]:
        """Load edge rows as in-memory ThoughtLink objects.

        Returns:
            list[ThoughtLink]: Graph edge payloads.
        """
        links: list[ThoughtLink] = []
        for row in self.list_edges():
            links.append(
                ThoughtLink(
                    id=row.id,
                    source_id=row.source_thought_id,
                    target_id=row.target_thought_id,
                    relation=RelationType(row.relation_type),
                    weight=row.weight,
                    metadata_json=dict(row.metadata_json),
                )
            )
        return links

    def _find_existing(self, payload: ThoughtLinkCreate) -> ThoughtEdge | None:
        """Find an edge matching source, target, and relation.

        Args:
            payload: Edge creation payload.

        Returns:
            ThoughtEdge | None: Existing row when found.
        """
        return (
            self.session.query(ThoughtEdge)
            .filter(
                ThoughtEdge.source_thought_id == payload.source_thought_id,
                ThoughtEdge.target_thought_id == payload.target_thought_id,
                ThoughtEdge.relation_type == str(payload.relation),
            )
            .one_or_none()
        )
