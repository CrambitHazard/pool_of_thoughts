"""Shared types for contextual salience adaptation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ContextWindow(StrEnum):
    """Temporal scope for contextual signals."""

    IMMEDIATE = "immediate"
    DAILY = "daily"
    LONG_TERM = "long_term"


@dataclass(frozen=True)
class ActivityRecord:
    """Single behavioral event tracked for context inference."""

    timestamp: datetime
    activity_type: str
    tags: tuple[str, ...] = ()
    thought_id: str | None = None
    content_hint: str = ""


@dataclass
class ContextState:
    """Aggregated contextual signals across temporal windows."""

    now: datetime
    immediate: dict[str, float] = field(default_factory=dict)
    daily: dict[str, float] = field(default_factory=dict)
    long_term: dict[str, float] = field(default_factory=dict)

    def signal(self, window: ContextWindow, name: str) -> float:
        """Return one signal strength from a context window.

        Args:
            window: Temporal scope to read.
            name: Signal identifier.

        Returns:
            float: Signal strength between 0.0 and 1.0.
        """
        bucket = {
            ContextWindow.IMMEDIATE: self.immediate,
            ContextWindow.DAILY: self.daily,
            ContextWindow.LONG_TERM: self.long_term,
        }[window]
        return bucket.get(name, 0.0)


@dataclass
class SalienceAdjustment:
    """Salience delta applied to one thought."""

    thought_id: str
    delta: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class ContextRecalcResult:
    """Summary of one contextual salience pass."""

    adjustments: list[SalienceAdjustment] = field(default_factory=list)
    active_signals: dict[str, float] = field(default_factory=dict)

    @property
    def changed_count(self) -> int:
        """Return the number of thoughts with non-zero adjustment.

        Returns:
            int: Count of adjusted thoughts.
        """
        return sum(1 for item in self.adjustments if item.delta != 0.0)


@dataclass(frozen=True)
class TriggerRule:
    """Maps an ambient context signal to thought content patterns."""

    signal: str
    window: ContextWindow
    content_patterns: tuple[str, ...]
    boost: float
    min_strength: float = 0.3
