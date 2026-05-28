"""Persistence helpers for memory abstractions."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.memory_abstraction import MemoryAbstraction
from app.models.schemas import MemoryAbstractionCreate, MemoryAbstractionRead


class MemoryAbstractionRepository:
    """CRUD access for consolidated semantic memories."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to a database session.

        Args:
            session: Active SQLAlchemy session.
        """
        self.session = session

    def add(
        self,
        payload: MemoryAbstractionCreate,
        now: datetime | None = None,
        abstraction_id: str | None = None,
    ) -> MemoryAbstractionRead:
        """Persist a new memory abstraction.

        Args:
            payload: Abstraction creation payload.
            now: Timestamp used for created_at and updated_at.
            abstraction_id: Optional deterministic identifier for tests.

        Returns:
            MemoryAbstractionRead: Persisted abstraction object.
        """
        current_time = now or datetime.now()
        abstraction = MemoryAbstraction(
            id=abstraction_id or str(uuid.uuid4()),
            summary=payload.summary,
            theme=payload.theme,
            confidence=payload.confidence,
            support_count=payload.support_count,
            source_thought_ids=list(payload.source_thought_ids),
            created_at=current_time,
            updated_at=current_time,
            metadata_json=deepcopy(payload.metadata_json),
        )
        self.session.add(abstraction)
        self.session.commit()
        self.session.refresh(abstraction)
        return MemoryAbstractionRead.model_validate(abstraction)

    def get(self, abstraction_id: str) -> MemoryAbstractionRead | None:
        """Fetch an abstraction by identifier.

        Args:
            abstraction_id: Abstraction primary key.

        Returns:
            MemoryAbstractionRead | None: Stored abstraction when found.
        """
        abstraction = self.session.get(MemoryAbstraction, abstraction_id)
        if abstraction is None:
            return None
        return MemoryAbstractionRead.model_validate(abstraction)

    def list_all(self) -> list[MemoryAbstractionRead]:
        """Return all stored abstractions ordered by recency.

        Returns:
            list[MemoryAbstractionRead]: Stored semantic memories.
        """
        rows = (
            self.session.query(MemoryAbstraction)
            .order_by(MemoryAbstraction.updated_at.desc())
            .all()
        )
        return [MemoryAbstractionRead.model_validate(row) for row in rows]

    def update(
        self,
        abstraction_id: str,
        payload: MemoryAbstractionCreate,
        now: datetime | None = None,
    ) -> MemoryAbstractionRead | None:
        """Update an existing abstraction record.

        Args:
            abstraction_id: Abstraction primary key.
            payload: Updated abstraction values.
            now: Timestamp for updated_at.

        Returns:
            MemoryAbstractionRead | None: Updated abstraction when found.
        """
        abstraction = self.session.get(MemoryAbstraction, abstraction_id)
        if abstraction is None:
            return None

        current_time = now or datetime.now()
        abstraction.summary = payload.summary
        abstraction.theme = payload.theme
        abstraction.confidence = payload.confidence
        abstraction.support_count = payload.support_count
        abstraction.source_thought_ids = list(payload.source_thought_ids)
        abstraction.updated_at = current_time
        abstraction.metadata_json = deepcopy(payload.metadata_json)
        self.session.commit()
        self.session.refresh(abstraction)
        return MemoryAbstractionRead.model_validate(abstraction)
