"""SQLAlchemy model for thought graph edges."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ThoughtEdge(Base):
    """Directed weighted edge between two thoughts."""

    __tablename__ = "thought_edges"
    __table_args__ = (
        UniqueConstraint(
            "source_thought_id",
            "target_thought_id",
            "relation_type",
            name="uq_thought_edge_relation",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    source_thought_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    target_thought_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
