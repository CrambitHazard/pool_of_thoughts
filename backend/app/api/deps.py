"""FastAPI dependency helpers."""

from functools import lru_cache

from sqlalchemy.orm import Session, sessionmaker

from app.cognitive.thought_extraction import ThoughtExtractionService
from app.cognitive.context.factory import build_context_engine
from app.config.settings import Settings, get_settings
from app.cognitive.context import ContextEngine
from app.memory.consolidation import ConsolidationService
from app.memory.graph import ThoughtGraph
from app.memory.graph.clustering import ClusteringConfig
from app.services.cognition_runtime import CognitionRuntime
from app.services.database import get_session_factory
from app.services.llm.factory import create_llm_provider


@lru_cache
def get_session_maker() -> sessionmaker[Session]:
    """Return a cached database session factory.

    Returns:
        sessionmaker[Session]: SQLAlchemy session factory.
    """
    return get_session_factory()


@lru_cache
def get_thought_extraction_service() -> ThoughtExtractionService:
    """Return a cached thought extraction service.

    Returns:
        ThoughtExtractionService: Configured extraction service.
    """
    settings = get_settings()
    provider = create_llm_provider(settings)
    return ThoughtExtractionService(provider, settings)


@lru_cache
def get_consolidation_service() -> ConsolidationService:
    """Return a cached consolidation service.

    Returns:
        ConsolidationService: Configured long-term memory consolidator.
    """
    settings = get_settings()
    provider = create_llm_provider(settings)
    return ConsolidationService(get_session_maker(), provider, settings)


@lru_cache
def get_thought_graph() -> ThoughtGraph:
    """Return a cached associative thought graph.

    Returns:
        ThoughtGraph: Configured graph with persistence and activation.
    """
    settings = get_settings()
    return ThoughtGraph(
        get_session_maker(),
        hop_decay=settings.graph_hop_decay,
        max_hops=settings.graph_max_hops,
        clustering_config=ClusteringConfig(min_cluster_size=settings.graph_cluster_min_size),
    )


@lru_cache
def get_context_engine() -> ContextEngine:
    """Return a cached contextual salience engine.

    Returns:
        ContextEngine: Shared activity log and rule engine.
    """
    return build_context_engine(get_settings())


@lru_cache
def get_cognition_runtime() -> CognitionRuntime:
    """Return the shared in-process cognition runtime.

    Returns:
        CognitionRuntime: Live cognition state manager.
    """
    return CognitionRuntime(
        extraction_service=get_thought_extraction_service(),
        thought_graph=get_thought_graph(),
        context_engine=get_context_engine(),
    )


def get_app_settings() -> Settings:
    """Return application settings for route handlers.

    Returns:
        Settings: Loaded configuration values.
    """
    return get_settings()
