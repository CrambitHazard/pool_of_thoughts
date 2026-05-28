"""Thought repository persistence tests."""

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.memory.repository import ThoughtRepository
from app.models.schemas import ThoughtCreate
from app.services.database import get_session_factory, init_db

NOW = datetime(2026, 5, 28, 12, 0, 0)


@pytest.fixture
def db_session(tmp_path: Path) -> Session:
    """Provide an isolated SQLite session for each test."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    session = get_session_factory(db_path)()
    yield session
    session.close()


def test_repository_persists_and_reads_thought(db_session: Session) -> None:
    """Repository writes and reads a thought record."""
    repository = ThoughtRepository(db_session)
    created = repository.add(
        ThoughtCreate(content="persist me", source="unit-test", salience=0.7),
        now=NOW,
        thought_id="persist-1",
    )

    loaded = repository.get("persist-1")

    assert created.id == "persist-1"
    assert loaded is not None
    assert loaded.content == "persist me"
    assert loaded.salience == 0.7


def test_repository_updates_and_deletes_thought(db_session: Session) -> None:
    """Repository can update salience and delete records."""
    repository = ThoughtRepository(db_session)
    repository.add(
        ThoughtCreate(content="mutable", source="unit-test"),
        now=NOW,
        thought_id="mutable-1",
    )

    updated = repository.update_salience("mutable-1", 0.25, now=NOW)
    deleted = repository.delete("mutable-1")

    assert updated is not None
    assert updated.salience == 0.25
    assert deleted is True
    assert repository.get("mutable-1") is None
