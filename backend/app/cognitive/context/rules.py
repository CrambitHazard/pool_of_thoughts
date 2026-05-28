"""Salience adjustment rules driven by contextual signals."""

from __future__ import annotations

from datetime import datetime

from app.cognitive.context.types import ActivityRecord, ContextState, ContextWindow, TriggerRule
from app.cognitive.similarity import ThoughtSimilarity
from app.models.schemas import ThoughtRead


def _thought_tokens(thought: ThoughtRead) -> set[str]:
    """Tokenize thought content for pattern checks.

    Args:
        thought: Thought to tokenize.

    Returns:
        set[str]: Normalized token set.
    """
    return ThoughtSimilarity.tokenize(thought.content)


def _matches_patterns(thought: ThoughtRead, patterns: tuple[str, ...]) -> bool:
    """Return whether thought content matches any trigger pattern.

    Args:
        thought: Thought being evaluated.
        patterns: Token or substring patterns.

    Returns:
        bool: True when a pattern matches.
    """
    if not patterns:
        return False

    tokens = _thought_tokens(thought)
    lowered = thought.content.lower()
    return any(pattern in tokens or pattern in lowered for pattern in patterns)


class UnresolvedDurationRule:
    """Boost unresolved thoughts that remain open over time."""

    name = "unresolved_duration"

    def __init__(
        self,
        hours_until_boost: float = 6.0,
        max_boost: float = 0.12,
    ) -> None:
        """Initialize unresolved duration rule thresholds.

        Args:
            hours_until_boost: Hours unresolved before salience increases.
            max_boost: Maximum salience boost from age alone.
        """
        self.hours_until_boost = hours_until_boost
        self.max_boost = max_boost

    def adjust(
        self,
        thought: ThoughtRead,
        state: ContextState,
        activities: list[ActivityRecord],
    ) -> tuple[float, list[str]]:
        """Increase salience for long-unresolved thoughts.

        Args:
            thought: Thought being evaluated.
            state: Aggregated contextual signals.
            activities: Unused for unresolved duration.

        Returns:
            tuple[float, list[str]]: Delta and reasons.
        """
        _ = (state, activities)
        if thought.resolved:
            return 0.0, []

        age_hours = (state.now - thought.created_at).total_seconds() / 3600.0
        if age_hours < self.hours_until_boost:
            return 0.0, []

        excess_hours = age_hours - self.hours_until_boost
        delta = min(self.max_boost, excess_hours * 0.01)
        return delta, [f"unresolved for {age_hours:.1f}h"]


class EmotionalThoughtRule:
    """Amplify emotionally weighted thoughts when ambient emotion is elevated."""

    name = "emotional_thought"

    def __init__(self, boost_factor: float = 0.15) -> None:
        """Initialize emotional thought rule.

        Args:
            boost_factor: Multiplier applied to thought emotional weight.
        """
        self.boost_factor = boost_factor

    def adjust(
        self,
        thought: ThoughtRead,
        state: ContextState,
        activities: list[ActivityRecord],
    ) -> tuple[float, list[str]]:
        """Boost salience for emotionally weighted thoughts in emotional context.

        Args:
            thought: Thought being evaluated.
            state: Aggregated contextual signals.
            activities: Unused for emotional weighting.

        Returns:
            tuple[float, list[str]]: Delta and reasons.
        """
        _ = activities
        ambient = state.signal(ContextWindow.IMMEDIATE, "emotion:ambient")
        if ambient <= 0.0 or thought.emotional_weight <= 0.0:
            return 0.0, []

        delta = min(0.2, thought.emotional_weight * ambient * self.boost_factor)
        return delta, ["emotional signal alignment"]


class RecurringThemeRule:
    """Boost thoughts aligned with recurring long-term behavioral patterns."""

    name = "recurring_theme"

    def __init__(self, boost: float = 0.08) -> None:
        """Initialize recurring theme rule.

        Args:
            boost: Salience boost when a recurring pattern matches.
        """
        self.boost = boost

    def adjust(
        self,
        thought: ThoughtRead,
        state: ContextState,
        activities: list[ActivityRecord],
    ) -> tuple[float, list[str]]:
        """Boost thoughts matching recurring behavioral themes.

        Args:
            thought: Thought being evaluated.
            state: Aggregated contextual signals.
            activities: Unused; patterns come from state signals.

        Returns:
            tuple[float, list[str]]: Delta and reasons.
        """
        _ = activities
        tokens = _thought_tokens(thought)
        reasons: list[str] = []
        delta = 0.0

        for signal_name, strength in state.long_term.items():
            if not signal_name.startswith("pattern:") or strength <= 0.0:
                continue
            tag = signal_name.removeprefix("pattern:")
            if tag in tokens or tag in thought.content.lower():
                delta += self.boost * strength
                reasons.append(f"recurring pattern:{tag}")

        return min(delta, 0.15), reasons


class TriggerActivationRule:
    """Apply configurable trigger boosts from ambient context signals."""

    name = "trigger_activation"

    def __init__(self, triggers: list[TriggerRule]) -> None:
        """Initialize trigger activation rule.

        Args:
            triggers: Trigger definitions mapping signals to content patterns.
        """
        self.triggers = triggers

    def adjust(
        self,
        thought: ThoughtRead,
        state: ContextState,
        activities: list[ActivityRecord],
    ) -> tuple[float, list[str]]:
        """Boost thoughts when trigger rules match current context.

        Args:
            thought: Thought being evaluated.
            state: Aggregated contextual signals.
            activities: Unused for trigger activation.

        Returns:
            tuple[float, list[str]]: Delta and reasons.
        """
        _ = activities
        delta = 0.0
        reasons: list[str] = []

        for trigger in self.triggers:
            strength = state.signal(trigger.window, trigger.signal)
            if strength < trigger.min_strength:
                continue
            if not _matches_patterns(thought, trigger.content_patterns):
                continue

            applied = trigger.boost * strength
            delta += applied
            reasons.append(f"trigger:{trigger.signal}")

        return min(delta, 0.2), reasons
