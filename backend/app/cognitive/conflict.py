"""Contradiction detection and salience adjustment."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.cognitive.similarity import ThoughtSimilarity
from app.models.schemas import ThoughtCreate, ThoughtRead

CONFLICT_MIN_SIMILARITY = 0.35
CONFLICT_SALIENCE_PENALTY = 0.15

NEGATION_WORDS = frozenset(
    {
        "not",
        "never",
        "no",
        "dont",
        "don't",
        "won't",
        "without",
        "none",
        "cannot",
        "can't",
    }
)

OPPOSITE_PAIRS = (
    ("increase", "decrease"),
    ("start", "stop"),
    ("enable", "disable"),
    ("always", "never"),
    ("yes", "no"),
    ("accept", "reject"),
    ("open", "close"),
)


@dataclass
class ConflictResolutionResult:
    """Summary of conflict adjustments applied to thoughts."""

    thoughts: list[ThoughtRead | ThoughtCreate]
    conflict_pairs: list[tuple[str, str]] = field(default_factory=list)


class ThoughtConflictResolver:
    """Reduce salience when contradictory thoughts coexist."""

    def __init__(
        self,
        similarity: ThoughtSimilarity | None = None,
        min_similarity: float = CONFLICT_MIN_SIMILARITY,
        salience_penalty: float = CONFLICT_SALIENCE_PENALTY,
    ) -> None:
        """Initialize the conflict resolver.

        Args:
            similarity: Similarity service used for contradiction checks.
            min_similarity: Minimum lexical overlap to consider a conflict.
            salience_penalty: Salience subtracted from each conflicting thought.
        """
        self.similarity = similarity or ThoughtSimilarity()
        self.min_similarity = min_similarity
        self.salience_penalty = salience_penalty

    def are_contradictory(
        self,
        left: ThoughtRead | ThoughtCreate,
        right: ThoughtRead | ThoughtCreate,
    ) -> bool:
        """Detect lightweight contradiction between two thoughts.

        Args:
            left: First thought object.
            right: Second thought object.

        Returns:
            bool: True when the thoughts appear contradictory.
        """
        overlap = self.similarity.score_thoughts(left, right)
        if overlap < self.min_similarity:
            return False

        left_tokens = self.similarity.tokenize(left.content)
        right_tokens = self.similarity.tokenize(right.content)
        left_negated = bool(left_tokens & NEGATION_WORDS)
        right_negated = bool(right_tokens & NEGATION_WORDS)

        if left_negated != right_negated:
            return True

        for first, second in OPPOSITE_PAIRS:
            if (first in left_tokens and second in right_tokens) or (
                second in left_tokens and first in right_tokens
            ):
                return True

        return False

    def resolve(
        self,
        thoughts: list[ThoughtRead | ThoughtCreate],
    ) -> ConflictResolutionResult:
        """Apply salience penalties for contradictory thought pairs.

        Args:
            thoughts: Thought set to evaluate, including incoming candidates.

        Returns:
            ConflictResolutionResult: Updated thoughts and conflict pair ids.
        """
        indexed: list[tuple[str, ThoughtRead | ThoughtCreate]] = []
        for index, thought in enumerate(thoughts):
            thought_id = getattr(thought, "id", None) or f"pending-{index}"
            indexed.append((thought_id, thought))

        updated = {thought_id: thought for thought_id, thought in indexed}
        conflict_pairs: list[tuple[str, str]] = []

        ordered_ids = sorted(updated.keys())
        for left_index, left_id in enumerate(ordered_ids):
            for right_id in ordered_ids[left_index + 1 :]:
                left = updated[left_id]
                right = updated[right_id]
                if not self.are_contradictory(left, right):
                    continue

                conflict_pairs.append((left_id, right_id))
                for thought_id in (left_id, right_id):
                    current = updated[thought_id]
                    updated[thought_id] = current.model_copy(
                        update={
                            "salience": max(
                                0.0,
                                current.salience - self.salience_penalty,
                            )
                        }
                    )

        return ConflictResolutionResult(
            thoughts=[updated[thought_id] for thought_id in ordered_ids],
            conflict_pairs=conflict_pairs,
        )
