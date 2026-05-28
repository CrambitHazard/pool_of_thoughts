"""SQLAlchemy model for cognitive thought objects."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Thought(Base):
    """Persistent thought object stored in SQLite."""

    __tablename__ = "thoughts"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    salience: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    emotional_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    novelty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    times_resurfaced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_accessed: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
