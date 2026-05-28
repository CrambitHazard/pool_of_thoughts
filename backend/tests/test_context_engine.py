"""Contextual salience adaptation tests."""

from datetime import datetime, timedelta

import pytest

from app.cognitive.context import (
    ActivityLog,
    ContextEngine,
    ContextEngineConfig,
    ContextWindow,
    TriggerRule,
)
from app.cognitive.context.providers import TimeOfDayProvider
from app.cognitive.context.rules import TriggerActivationRule, UnresolvedDurationRule
from app.models.schemas import ThoughtRead

NOW = datetime(2026, 5, 28, 22, 30, 0)


def make_thought(
    thought_id: str,
    content: str,
    *,
    salience: float = 0.5,
    emotional_weight: float = 0.0,
    created_at: datetime | None = None,
    resolved: bool = False,
) -> ThoughtRead:
    """Build a thought for context tests."""
    created = created_at or NOW
    return ThoughtRead(
        id=thought_id,
        content=content,
        source="test",
        salience=salience,
        emotional_weight=emotional_weight,
        novelty=0.0,
        resolved=resolved,
        created_at=created,
        expires_at=None,
        times_resurfaced=0,
        last_accessed=created,
        metadata_json={},
    )


def test_time_of_day_provider_sets_night_signal() -> None:
    """Nighttime maps to the night contextual signal."""
    provider = TimeOfDayProvider()
    signals = provider.collect([], [], NOW)

    assert signals["time:night"] == 1.0
    assert signals["time:morning"] == 0.0


def test_activity_log_infers_coding_tags() -> None:
    """Recent coding activity is tagged without user-specific rules."""
    log = ActivityLog()
    entry = log.record(
        "thought_added",
        NOW,
        content_hint="Continue Rust programming debug session",
    )

    assert "coding" in entry.tags


def test_trigger_boosts_programming_thoughts_during_coding_activity() -> None:
    """Coding activity boosts programming-related thoughts."""
    log = ActivityLog()
    log.record("thought_added", NOW, content_hint="debug rust programming module")

    engine = ContextEngine(
        activity_log=log,
        rules=[TriggerActivationRule([
            TriggerRule(
                signal="activity:coding",
                window=ContextWindow.IMMEDIATE,
                content_patterns=("program", "rust", "code"),
                boost=0.2,
            ),
        ])],
        config=ContextEngineConfig(max_adjustment=0.25),
    )

    thoughts = [
        make_thought("code-thought", "Finish Rust programming module"),
        make_thought("other", "Buy groceries"),
    ]
    updated, result = engine.recalculate(thoughts, now=NOW)

    code_thought = next(item for item in updated if item.id == "code-thought")
    other = next(item for item in updated if item.id == "other")

    assert code_thought.salience > other.salience
    assert result.changed_count >= 1


def test_trigger_boosts_reflective_thoughts_at_night() -> None:
    """Nighttime context boosts reflective thoughts."""
    engine = ContextEngine(
        rules=[TriggerActivationRule([
            TriggerRule(
                signal="time:night",
                window=ContextWindow.IMMEDIATE,
                content_patterns=("reflect", "review", "journal"),
                boost=0.15,
            ),
        ])],
    )

    thoughts = [
        make_thought("reflect", "Evening journal reflection"),
        make_thought("task", "Send invoice"),
    ]
    updated, _result = engine.recalculate(thoughts, now=NOW)

    reflective = next(item for item in updated if item.id == "reflect")
    task = next(item for item in updated if item.id == "task")

    assert reflective.salience > task.salience


def test_unresolved_duration_increases_salience() -> None:
    """Long-unresolved thoughts receive a salience boost."""
    old_created = NOW - timedelta(hours=12)
    engine = ContextEngine(rules=[UnresolvedDurationRule(hours_until_boost=6.0, max_boost=0.12)])

    thoughts = [make_thought("old", "Open task still pending", created_at=old_created)]
    updated, result = engine.recalculate(thoughts, now=NOW)

    assert updated[0].salience > 0.5
    assert result.adjustments[0].delta > 0.0


def test_context_engine_respects_recalc_interval() -> None:
    """Periodic recalculation respects configured intervals."""
    engine = ContextEngine()
    assert engine.should_recalculate(NOW, interval_minutes=5.0) is True

    engine.recalculate([], now=NOW)
    assert engine.should_recalculate(NOW + timedelta(minutes=2), interval_minutes=5.0) is False
    assert engine.should_recalculate(NOW + timedelta(minutes=6), interval_minutes=5.0) is True


def test_context_windows_aggregate_separate_signals() -> None:
    """Immediate, daily, and long-term windows keep separate signal buckets."""
    log = ActivityLog()
    log.record("thought_added", NOW - timedelta(days=10), content_hint="coding rust project")
    log.record("thought_added", NOW - timedelta(days=9), content_hint="coding rust module")
    log.record("thought_added", NOW - timedelta(days=8), content_hint="coding rust tests")
    log.record("thought_added", NOW, content_hint="reflective journal entry")

    engine = ContextEngine(
        activity_log=log,
        config=ContextEngineConfig(
            immediate_minutes=30,
            daily_hours=24,
            long_term_days=14,
            recurring_min_occurrences=3,
        ),
    )
    state = engine.build_state([], now=NOW)

    assert any(key.startswith("activity:") for key in state.immediate)
    assert any(key.startswith("daily:") for key in state.daily)
    assert any(key.startswith("pattern:") for key in state.long_term)


def test_emotional_rule_boosts_weighted_thoughts_in_emotional_context() -> None:
    """Emotionally weighted thoughts gain salience when ambient emotion is high."""
    from app.cognitive.context.providers import EmotionalSignalsProvider
    from app.cognitive.context.rules import EmotionalThoughtRule

    engine = ContextEngine(
        providers=[EmotionalSignalsProvider()],
        rules=[EmotionalThoughtRule(boost_factor=0.5)],
    )

    thoughts = [
        make_thought("charged", "Important decision", emotional_weight=0.9, salience=0.5),
        make_thought("neutral", "Routine note", emotional_weight=0.0, salience=0.5),
    ]
    updated, _result = engine.recalculate(thoughts, now=NOW)

    charged = next(item for item in updated if item.id == "charged")
    neutral = next(item for item in updated if item.id == "neutral")

    assert charged.salience >= neutral.salience
