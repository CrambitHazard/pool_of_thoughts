"""SQLite database engine and session helpers."""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "laguna.db"


def get_engine(db_path: Path | str | None = None):
    """Create a SQLite engine for the given database path.

    Args:
        db_path: Optional filesystem path for the SQLite file.

    Returns:
        sqlalchemy.Engine: Configured database engine.
    """
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    return create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
    )


def get_session_factory(db_path: Path | str | None = None):
    """Create a session factory bound to the SQLite engine.

    Args:
        db_path: Optional filesystem path for the SQLite file.

    Returns:
        sqlalchemy.orm.sessionmaker: Session factory.
    """
    engine = get_engine(db_path)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db(db_path: Path | str | None = None) -> None:
    """Create all database tables if they do not exist.

    Args:
        db_path: Optional filesystem path for the SQLite file.

    Returns:
        None
    """
    engine = get_engine(db_path)
    Base.metadata.create_all(bind=engine)


def get_db_session(db_path: Path | str | None = None) -> Generator[Session, None, None]:
    """Yield a database session for request-scoped usage.

    Args:
        db_path: Optional filesystem path for the SQLite file.

    Yields:
        Session: Active SQLAlchemy session.
    """
    session_factory = get_session_factory(db_path)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
