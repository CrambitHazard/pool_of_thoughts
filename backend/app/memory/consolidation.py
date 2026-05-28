"""Long-term memory consolidation from recent episodic thoughts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session, sessionmaker

from app.cognitive.reflection_prompts import REFLECTION_SYSTEM_PROMPT, build_abstraction_prompt
from app.cognitive.similarity import ThoughtSimilarity
from app.config.settings import Settings, get_settings
from app.memory.abstraction_repository import MemoryAbstractionRepository
from app.memory.repository import ThoughtRepository
from app.models.schemas import MemoryAbstractionCreate, MemoryAbstractionRead, ThoughtRead
from app.services.llm.base import LLMProvider

THEME_CLUSTER_SIMILARITY = 0.35
THEME_SHARED_TOKEN_MIN = 2
ABSTRACTION_DUPLICATE_THRESHOLD = 0.7

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "to",
        "and",
        "or",
        "i",
        "me",
        "my",
        "want",
        "watched",
        "is",
        "are",
        "was",
        "were",
        "in",
        "on",
        "for",
        "of",
        "it",
        "that",
        "this",
    }
)


class GeneratedAbstraction(BaseModel):
    """LLM output schema for semantic memory generation."""

    summary: str = Field(min_length=1, max_length=500)
    theme: str = Field(min_length=1, max_length=255)
    confidence: float = Field(ge=0.0, le=1.0)


@dataclass
class ThemeCluster:
    """Heuristically detected group of related recent thoughts."""

    theme_hint: str
    thoughts: list[ThoughtRead]

    @property
    def thought_ids(self) -> list[str]:
        """Return thought ids in the cluster.

        Returns:
            list[str]: Cluster member ids.
        """
        return [thought.id for thought in self.thoughts]


@dataclass
class ConsolidationResult:
    """Summary of one consolidation pass."""

    reviewed_thoughts: int = 0
    theme_clusters: int = 0
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    consolidated_thought_ids: list[str] = field(default_factory=list)


class ConsolidationService:
    """Review recent thoughts and store compressed semantic memories."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        provider: LLMProvider,
        settings: Settings | None = None,
        similarity: ThoughtSimilarity | None = None,
    ) -> None:
        """Initialize the consolidation service.

        Args:
            session_factory: Database session factory.
            provider: LLM provider used only for abstraction generation.
            settings: Optional settings override.
            similarity: Similarity helper for clustering and deduplication.
        """
        self.session_factory = session_factory
        self.provider = provider
        self.settings = settings or get_settings()
        self.similarity = similarity or ThoughtSimilarity()

    async def consolidate(self, now: datetime | None = None) -> ConsolidationResult:
        """Review recent thoughts and create or update semantic abstractions.

        Args:
            now: Reference time for lookback and timestamps.

        Returns:
            ConsolidationResult: Summary of consolidation actions.
        """
        current_time = now or datetime.now()
        result = ConsolidationResult()
        session = self.session_factory()

        try:
            thought_repo = ThoughtRepository(session)
            abstraction_repo = MemoryAbstractionRepository(session)
            since = current_time - timedelta(hours=self.settings.reflection_lookback_hours)
            recent = thought_repo.list_recent(
                since=since,
                limit=self.settings.reflection_max_thoughts,
                exclude_consolidated=True,
            )
            result.reviewed_thoughts = len(recent)

            clusters = self.detect_theme_clusters(recent)
            result.theme_clusters = len(clusters)

            for cluster in clusters[: self.settings.reflection_max_clusters_per_run]:
                generated = await self._generate_abstraction(cluster)
                stored = self._store_abstraction(
                    abstraction_repo,
                    generated,
                    cluster,
                    current_time,
                )
                if stored.metadata_json.get("updated_existing"):
                    result.updated.append(stored.id)
                else:
                    result.created.append(stored.id)

                thought_repo.mark_consolidated(
                    cluster.thought_ids,
                    stored.id,
                    now=current_time,
                )
                result.consolidated_thought_ids.extend(cluster.thought_ids)

            return result
        finally:
            session.close()

    def detect_theme_clusters(self, thoughts: list[ThoughtRead]) -> list[ThemeCluster]:
        """Group recent thoughts into recurring theme clusters.

        Args:
            thoughts: Recent episodic thoughts to analyze.

        Returns:
            list[ThemeCluster]: Clusters meeting the minimum size threshold.
        """
        if not thoughts:
            return []

        used: set[str] = set()
        clusters: list[ThemeCluster] = []

        for anchor in sorted(thoughts, key=lambda thought: (thought.created_at, thought.id)):
            if anchor.id in used:
                continue

            members = [anchor]
            used.add(anchor.id)

            for candidate in thoughts:
                if candidate.id in used:
                    continue
                if any(
                    self._thoughts_related(candidate, member)
                    for member in members
                ):
                    members.append(candidate)
                    used.add(candidate.id)

            if len(members) < self.settings.reflection_min_cluster_size:
                continue

            members.sort(key=lambda thought: (thought.created_at, thought.id))
            clusters.append(
                ThemeCluster(
                    theme_hint=self._build_theme_hint(members),
                    thoughts=members,
                )
            )

        clusters.sort(key=lambda cluster: (-len(cluster.thoughts), cluster.theme_hint))
        return clusters

    def _thoughts_related(self, left: ThoughtRead, right: ThoughtRead) -> bool:
        """Check whether two thoughts belong to the same recurring theme.

        Args:
            left: First thought object.
            right: Second thought object.

        Returns:
            bool: True when the thoughts should cluster together.
        """
        if (
            self.similarity.score_thoughts(left, right) >= THEME_CLUSTER_SIMILARITY
        ):
            return True

        left_tokens = self._significant_tokens(left.content)
        right_tokens = self._significant_tokens(right.content)
        return len(left_tokens & right_tokens) >= THEME_SHARED_TOKEN_MIN

    @staticmethod
    def _significant_tokens(content: str) -> set[str]:
        """Extract meaningful tokens from thought content.

        Args:
            content: Thought text.

        Returns:
            set[str]: Significant tokens used for theme grouping.
        """
        return {
            token
            for token in ThoughtSimilarity.tokenize(content)
            if token not in _STOPWORDS and len(token) >= 3
        }

    async def _generate_abstraction(self, cluster: ThemeCluster) -> GeneratedAbstraction:
        """Use the LLM to compress a theme cluster into semantic memory.

        Args:
            cluster: Related thoughts identified by heuristics.

        Returns:
            GeneratedAbstraction: Parsed abstraction payload.

        Raises:
            ValidationError: When the LLM output is invalid.
        """
        prompt = build_abstraction_prompt(
            [thought.content for thought in cluster.thoughts],
            cluster.theme_hint,
        )
        raw_json = await self.provider.complete_json(REFLECTION_SYSTEM_PROMPT, prompt)
        payload = _parse_json_response(raw_json)
        return GeneratedAbstraction.model_validate(payload)

    def _store_abstraction(
        self,
        repository: MemoryAbstractionRepository,
        generated: GeneratedAbstraction,
        cluster: ThemeCluster,
        now: datetime,
    ) -> MemoryAbstractionRead:
        """Persist or update a semantic abstraction record.

        Args:
            repository: Abstraction repository bound to the active session.
            generated: LLM-generated abstraction payload.
            cluster: Source thought cluster.
            now: Timestamp for persistence.

        Returns:
            MemoryAbstractionRead: Stored semantic memory.
        """
        payload = MemoryAbstractionCreate(
            summary=generated.summary,
            theme=generated.theme,
            confidence=generated.confidence,
            support_count=len(cluster.thoughts),
            source_thought_ids=cluster.thought_ids,
            metadata_json={"theme_hint": cluster.theme_hint},
        )

        for existing in repository.list_all():
            if self.similarity.score(existing.summary, payload.summary) >= ABSTRACTION_DUPLICATE_THRESHOLD:
                merged_ids = sorted(set(existing.source_thought_ids) | set(payload.source_thought_ids))
                updated_payload = MemoryAbstractionCreate(
                    summary=payload.summary,
                    theme=payload.theme,
                    confidence=max(existing.confidence, payload.confidence),
                    support_count=len(merged_ids),
                    source_thought_ids=merged_ids,
                    metadata_json={
                        **existing.metadata_json,
                        "theme_hint": cluster.theme_hint,
                        "updated_existing": True,
                    },
                )
                updated = repository.update(existing.id, updated_payload, now=now)
                if updated is not None:
                    return updated

        return repository.add(payload, now=now)

    @staticmethod
    def _build_theme_hint(thoughts: list[ThoughtRead]) -> str:
        """Build a deterministic theme hint from recurring tokens.

        Args:
            thoughts: Cluster member thoughts.

        Returns:
            str: Short theme hint used in the abstraction prompt.
        """
        counts: dict[str, int] = {}
        for thought in thoughts:
            for token in ThoughtSimilarity.tokenize(thought.content):
                if token in _STOPWORDS or len(token) < 3:
                    continue
                counts[token] = counts.get(token, 0) + 1

        if not counts:
            return "recurring thoughts"

        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        top_tokens = [token for token, _count in ranked[:3]]
        return " ".join(top_tokens)


def _parse_json_response(raw: str) -> dict:
    """Parse JSON from an LLM response.

    Args:
        raw: Raw model output.

    Returns:
        dict: Parsed JSON object.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise TypeError("Abstraction payload must be a JSON object.")
    return data
