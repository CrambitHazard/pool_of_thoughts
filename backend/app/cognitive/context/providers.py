"""Context providers for ambient signal collection."""

from __future__ import annotations

from datetime import datetime

from app.cognitive.context.types import ActivityRecord, ContextWindow
from app.cognitive.similarity import ThoughtSimilarity
from app.models.schemas import ThoughtRead


def _clamp(value: float, upper: float = 1.0) -> float:
    """Clamp a signal strength to a valid range.

    Args:
        value: Raw signal value.
        upper: Maximum allowed value.

    Returns:
        float: Clamped signal strength.
    """
    return max(0.0, min(upper, value))


class TimeOfDayProvider:
    """Expose time-of-day signals for immediate and daily windows."""

    name = "time_of_day"
    window = ContextWindow.IMMEDIATE

    def collect(
        self,
        activities: list[ActivityRecord],
        thoughts: list[ThoughtRead],
        now: datetime,
    ) -> dict[str, float]:
        """Collect time-of-day contextual signals.

        Args:
            activities: Unused for clock-based inference.
            thoughts: Unused for clock-based inference.
            now: Reference timestamp.

        Returns:
            dict[str, float]: Time period signal strengths.
        """
        _ = (activities, thoughts)
        hour = now.hour
        signals = {
            "time:morning": 0.0,
            "time:afternoon": 0.0,
            "time:evening": 0.0,
            "time:night": 0.0,
        }

        if 5 <= hour < 12:
            signals["time:morning"] = 1.0
        elif 12 <= hour < 17:
            signals["time:afternoon"] = 1.0
        elif 17 <= hour < 22:
            signals["time:evening"] = 1.0
        else:
            signals["time:night"] = 1.0

        return signals


class RecentActivityProvider:
    """Summarize recent behavioral tags in the immediate window."""

    name = "recent_activity"
    window = ContextWindow.IMMEDIATE

    def collect(
        self,
        activities: list[ActivityRecord],
        thoughts: list[ThoughtRead],
        now: datetime,
    ) -> dict[str, float]:
        """Collect recent activity tag strengths.

        Args:
            activities: Immediate-window activity records.
            thoughts: Unused for activity inference.
            now: Reference timestamp.

        Returns:
            dict[str, float]: Activity signal strengths.
        """
        _ = (thoughts, now)
        counts: dict[str, int] = {}
        for entry in activities:
            for tag in entry.tags:
                counts[tag] = counts.get(tag, 0) + 1

        if not counts:
            return {}

        peak = max(counts.values())
        return {f"activity:{tag}": _clamp(count / max(peak, 1)) for tag, count in counts.items()}


class RecurringBehaviorProvider:
    """Detect recurring activity patterns over the long-term window."""

    name = "recurring_behavior"
    window = ContextWindow.LONG_TERM

    def __init__(self, min_occurrences: int = 3) -> None:
        """Initialize the recurring behavior provider.

        Args:
            min_occurrences: Minimum tag count treated as a recurring pattern.
        """
        self.min_occurrences = min_occurrences

    def collect(
        self,
        activities: list[ActivityRecord],
        thoughts: list[ThoughtRead],
        now: datetime,
    ) -> dict[str, float]:
        """Collect recurring behavioral pattern strengths.

        Args:
            activities: Long-term activity records.
            thoughts: Unused for recurrence inference.
            now: Reference timestamp.

        Returns:
            dict[str, float]: Recurring pattern signal strengths.
        """
        _ = (thoughts, now)
        counts: dict[str, int] = {}
        for entry in activities:
            for tag in entry.tags:
                counts[tag] = counts.get(tag, 0) + 1

        signals: dict[str, float] = {}
        for tag, count in counts.items():
            if count < self.min_occurrences:
                continue
            signals[f"pattern:{tag}"] = _clamp(count / (count + 2))

        return signals


class DailyActivityProvider:
    """Aggregate daily activity tags for the daily context window."""

    name = "daily_activity"
    window = ContextWindow.DAILY

    def collect(
        self,
        activities: list[ActivityRecord],
        thoughts: list[ThoughtRead],
        now: datetime,
    ) -> dict[str, float]:
        """Collect daily activity tag strengths.

        Args:
            activities: Daily-window activity records.
            thoughts: Unused for activity inference.
            now: Reference timestamp.

        Returns:
            dict[str, float]: Daily activity signal strengths.
        """
        _ = (thoughts, now)
        counts: dict[str, int] = {}
        for entry in activities:
            for tag in entry.tags:
                counts[tag] = counts.get(tag, 0) + 1

        if not counts:
            return {}

        total = sum(counts.values())
        return {
            f"daily:{tag}": _clamp(count / total)
            for tag, count in counts.items()
        }


class EmotionalSignalsProvider:
    """Summarize recent emotional intensity from thought payloads."""

    name = "emotional_signals"
    window = ContextWindow.IMMEDIATE

    def collect(
        self,
        activities: list[ActivityRecord],
        thoughts: list[ThoughtRead],
        now: datetime,
    ) -> dict[str, float]:
        """Collect ambient emotional signal strength.

        Args:
            activities: Immediate-window activity records.
            thoughts: Active thoughts with emotional weights.
            now: Reference timestamp.

        Returns:
            dict[str, float]: Emotional context signals.
        """
        _ = (activities, now)
        if not thoughts:
            return {"emotion:ambient": 0.0}

        average = sum(thought.emotional_weight for thought in thoughts) / len(thoughts)
        peak = max(thought.emotional_weight for thought in thoughts)
        return {
            "emotion:ambient": _clamp(average),
            "emotion:peak": _clamp(peak),
        }
