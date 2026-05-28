"""SQLAlchemy model for mechanically detected theme clusters."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ThoughtCluster(Base):
    """Persisted grouping of recurring thematic thoughts."""

    __tablename__ = "thought_clusters"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    thought_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    cohesion: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
