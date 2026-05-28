"""Heuristic similarity scoring for thought objects."""

from __future__ import annotations

import re

from app.models.schemas import ThoughtCreate, ThoughtRead

MERGE_SIMILARITY_THRESHOLD = 0.65

_TOKEN_PATTERN = re.compile(r"[a-z0-9']+")


class ThoughtSimilarity:
    """Lightweight lexical similarity without embeddings."""

    def __init__(self, merge_threshold: float = MERGE_SIMILARITY_THRESHOLD) -> None:
        """Initialize the similarity service.

        Args:
            merge_threshold: Minimum score required to treat thoughts as similar.
        """
        self.merge_threshold = merge_threshold

    def score(self, left: str, right: str) -> float:
        """Score lexical similarity between two text strings.

        Args:
            left: First text value.
            right: Second text value.

        Returns:
            float: Similarity score between 0.0 and 1.0.
        """
        left_tokens = self.tokenize(left)
        right_tokens = self.tokenize(right)

        if not left_tokens or not right_tokens:
            return 0.0

        intersection = left_tokens & right_tokens
        union = left_tokens | right_tokens
        jaccard = len(intersection) / len(union)

        left_norm = " ".join(sorted(left_tokens))
        right_norm = " ".join(sorted(right_tokens))
        if left_norm in right_norm or right_norm in left_norm:
            return max(jaccard, 0.75)

        return jaccard

    def score_thoughts(
        self,
        left: ThoughtRead | ThoughtCreate,
        right: ThoughtRead | ThoughtCreate,
    ) -> float:
        """Score similarity between two thought objects.

        Args:
            left: First thought object.
            right: Second thought object.

        Returns:
            float: Similarity score between 0.0 and 1.0.
        """
        return self.score(left.content, right.content)

    def find_best_match(
        self,
        candidate: ThoughtCreate | ThoughtRead,
        thoughts: list[ThoughtRead],
    ) -> tuple[ThoughtRead | None, float]:
        """Find the most similar thought above zero similarity.

        Args:
            candidate: Incoming thought candidate.
            thoughts: Existing thoughts to compare against.

        Returns:
            tuple[ThoughtRead | None, float]: Best match and its score.
        """
        best_thought: ThoughtRead | None = None
        best_score = 0.0

        for thought in thoughts:
            current_score = self.score_thoughts(candidate, thought)
            if current_score <= 0:
                continue
            if best_thought is None or current_score > best_score or (
                current_score == best_score and thought.id < best_thought.id
            ):
                best_score = current_score
                best_thought = thought

        if best_score == 0.0:
            return None, 0.0
        return best_thought, best_score

    def should_merge(
        self,
        candidate: ThoughtCreate | ThoughtRead,
        thoughts: list[ThoughtRead],
    ) -> tuple[ThoughtRead | None, float]:
        """Return a merge target when similarity exceeds the threshold.

        Args:
            candidate: Incoming thought candidate.
            thoughts: Existing thoughts to compare against.

        Returns:
            tuple[ThoughtRead | None, float]: Merge target and score when eligible.
        """
        match, score = self.find_best_match(candidate, thoughts)
        if match is None or score < self.merge_threshold:
            return None, score
        return match, score

    @staticmethod
    def tokenize(text: str) -> set[str]:
        """Tokenize text into a normalized word set.

        Args:
            text: Input text.

        Returns:
            set[str]: Token set used for similarity scoring.
        """
        return set(_TOKEN_PATTERN.findall(text.lower()))
