"""Persistence helpers for thought objects."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.schemas import ThoughtCreate, ThoughtRead
from app.models.thought import Thought


class ThoughtRepository:
    """CRUD access for persisted thought records."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to a database session.

        Args:
            session: Active SQLAlchemy session.
        """
        self.session = session

    def add(
        self,
        payload: ThoughtCreate,
        now: datetime | None = None,
        thought_id: str | None = None,
    ) -> ThoughtRead:
        """Persist a new thought record.

        Args:
            payload: Thought creation payload.
            now: Timestamp used for created_at and last_accessed.
            thought_id: Optional deterministic identifier for tests.

        Returns:
            ThoughtRead: Persisted thought object.
        """
        current_time = now or datetime.now()
        thought = Thought(
            id=thought_id or str(uuid.uuid4()),
            content=payload.content,
            source=payload.source,
            salience=payload.salience,
            emotional_weight=payload.emotional_weight,
            novelty=payload.novelty,
            resolved=payload.resolved,
            created_at=current_time,
            expires_at=payload.expires_at,
            times_resurfaced=0,
            last_accessed=current_time,
            metadata_json=deepcopy(payload.metadata_json),
        )
        self.session.add(thought)
        self.session.commit()
        self.session.refresh(thought)
        return ThoughtRead.model_validate(thought)

    def get(self, thought_id: str) -> ThoughtRead | None:
        """Fetch a thought by identifier.

        Args:
            thought_id: Thought primary key.

        Returns:
            ThoughtRead | None: Stored thought when found.
        """
        thought = self.session.get(Thought, thought_id)
        if thought is None:
            return None
        return ThoughtRead.model_validate(thought)

    def update_salience(
        self,
        thought_id: str,
        salience: float,
        now: datetime | None = None,
    ) -> ThoughtRead | None:
        """Update salience for a persisted thought.

        Args:
            thought_id: Thought primary key.
            salience: New salience value.
            now: Optional timestamp for last_accessed.

        Returns:
            ThoughtRead | None: Updated thought when found.
        """
        thought = self.session.get(Thought, thought_id)
        if thought is None:
            return None

        current_time = now or datetime.now()
        thought.salience = salience
        thought.last_accessed = current_time
        self.session.commit()
        self.session.refresh(thought)
        return ThoughtRead.model_validate(thought)

    def delete(self, thought_id: str) -> bool:
        """Delete a thought record.

        Args:
            thought_id: Thought primary key.

        Returns:
            bool: True when a record was deleted.
        """
        thought = self.session.get(Thought, thought_id)
        if thought is None:
            return False

        self.session.delete(thought)
        self.session.commit()
        return True

    def list_recent(
        self,
        since: datetime | None = None,
        limit: int = 100,
        exclude_consolidated: bool = True,
    ) -> list[ThoughtRead]:
        """List recent thoughts for reflection and consolidation.

        Args:
            since: Optional lower bound for created_at.
            limit: Maximum number of thoughts to return.
            exclude_consolidated: Skip thoughts already linked to abstractions.

        Returns:
            list[ThoughtRead]: Recent thought records ordered oldest first.
        """
        query = self.session.query(Thought)
        if since is not None:
            query = query.filter(Thought.created_at >= since)
        rows = query.order_by(Thought.created_at.asc()).limit(limit).all()

        thoughts: list[ThoughtRead] = []
        for row in rows:
            thought = ThoughtRead.model_validate(row)
            if exclude_consolidated and thought.metadata_json.get("consolidated"):
                continue
            thoughts.append(thought)
        return thoughts

    def mark_consolidated(
        self,
        thought_ids: list[str],
        abstraction_id: str,
        now: datetime | None = None,
    ) -> int:
        """Mark source thoughts as consolidated into long-term memory.

        Args:
            thought_ids: Thought ids absorbed by an abstraction.
            abstraction_id: Resulting abstraction identifier.
            now: Timestamp recorded in thought metadata.

        Returns:
            int: Number of thoughts updated.
        """
        current_time = now or datetime.now()
        updated = 0

        for thought_id in thought_ids:
            thought = self.session.get(Thought, thought_id)
            if thought is None:
                continue
            metadata = dict(thought.metadata_json)
            metadata["consolidated"] = True
            metadata["abstraction_id"] = abstraction_id
            metadata["consolidated_at"] = current_time.isoformat()
            thought.metadata_json = metadata
            updated += 1

        if updated:
            self.session.commit()
        return updated
