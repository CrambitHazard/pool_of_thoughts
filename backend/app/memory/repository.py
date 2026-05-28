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
