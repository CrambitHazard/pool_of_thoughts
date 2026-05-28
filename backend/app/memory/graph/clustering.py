"""Mechanical theme clustering for associative graphs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.cognitive.similarity import ThoughtSimilarity
from app.memory.graph.types import GraphThemeCluster
from app.models.graph_types import RelationType
from app.models.schemas import ThoughtRead

THEME_CLUSTER_SIMILARITY = 0.35
THEME_SHARED_TOKEN_MIN = 2

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


@dataclass
class ClusteringConfig:
    """Thresholds for graph theme clustering."""

    min_cluster_size: int = 2
    similarity_threshold: float = THEME_CLUSTER_SIMILARITY
    shared_token_min: int = THEME_SHARED_TOKEN_MIN


class GraphClusteringService:
    """Group recurring themes using lexical overlap, not embeddings."""

    def __init__(
        self,
        similarity: ThoughtSimilarity | None = None,
        config: ClusteringConfig | None = None,
    ) -> None:
        """Initialize the clustering service.

        Args:
            similarity: Lexical similarity helper.
            config: Clustering thresholds.
        """
        self.similarity = similarity or ThoughtSimilarity()
        self.config = config or ClusteringConfig()

    def detect_clusters(self, thoughts: list[ThoughtRead]) -> list[GraphThemeCluster]:
        """Detect recurring theme clusters from thought content.

        Args:
            thoughts: Candidate thoughts to cluster.

        Returns:
            list[GraphThemeCluster]: Clusters meeting the minimum size threshold.
        """
        if not thoughts:
            return []

        used: set[str] = set()
        clusters: list[GraphThemeCluster] = []

        for anchor in sorted(thoughts, key=lambda thought: (thought.created_at, thought.id)):
            if anchor.id in used:
                continue

            members = [anchor]
            used.add(anchor.id)

            for candidate in thoughts:
                if candidate.id in used:
                    continue
                if any(self._thoughts_related(candidate, member) for member in members):
                    members.append(candidate)
                    used.add(candidate.id)

            if len(members) < self.config.min_cluster_size:
                continue

            members.sort(key=lambda thought: (thought.created_at, thought.id))
            clusters.append(self._build_cluster(members))

        clusters.sort(key=lambda cluster: (-len(cluster.thought_ids), cluster.label))
        return clusters

    def suggested_links(
        self,
        cluster: GraphThemeCluster,
        weight: float = 0.6,
    ) -> list[tuple[str, str, RelationType, float]]:
        """Suggest related_to edges for all pairs in a cluster.

        Args:
            cluster: Theme cluster.
            weight: Edge weight for intra-cluster links.

        Returns:
            list[tuple[str, str, RelationType, float]]: Source, target, relation, weight.
        """
        links: list[tuple[str, str, RelationType, float]] = []
        ids = cluster.thought_ids
        for index, source_id in enumerate(ids):
            for target_id in ids[index + 1 :]:
                links.append((source_id, target_id, RelationType.RELATED_TO, weight))
        return links

    def _thoughts_related(self, left: ThoughtRead, right: ThoughtRead) -> bool:
        """Return whether two thoughts belong to the same theme cluster.

        Args:
            left: First thought.
            right: Second thought.

        Returns:
            bool: True when thoughts should cluster together.
        """
        if self.similarity.score_thoughts(left, right) >= self.config.similarity_threshold:
            return True

        left_tokens = self._significant_tokens(left.content)
        right_tokens = self._significant_tokens(right.content)
        return len(left_tokens & right_tokens) >= self.config.shared_token_min

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

    def _build_cluster(self, members: list[ThoughtRead]) -> GraphThemeCluster:
        """Build a persisted cluster object from member thoughts.

        Args:
            members: Cluster member thoughts.

        Returns:
            GraphThemeCluster: Detected theme cluster.
        """
        scores: list[float] = []
        for index, left in enumerate(members):
            for right in members[index + 1 :]:
                scores.append(self.similarity.score_thoughts(left, right))

        cohesion = sum(scores) / len(scores) if scores else 0.0
        return GraphThemeCluster(
            id=str(uuid.uuid4()),
            label=self._build_label(members),
            thought_ids=[thought.id for thought in members],
            cohesion=round(cohesion, 4),
            metadata_json={"member_count": len(members)},
        )

    @staticmethod
    def _build_label(thoughts: list[ThoughtRead]) -> str:
        """Build a deterministic cluster label from recurring tokens.

        Args:
            thoughts: Cluster member thoughts.

        Returns:
            str: Short cluster label.
        """
        counts: dict[str, int] = {}
        for thought in thoughts:
            for token in ThoughtSimilarity.tokenize(thought.content):
                if token in _STOPWORDS or len(token) < 3:
                    continue
                counts[token] = counts.get(token, 0) + 1

        if not counts:
            return "recurring themes"

        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        top_tokens = [token for token, _count in ranked[:3]]
        return " ".join(top_tokens)
