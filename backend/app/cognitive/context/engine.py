"""ContextEngine orchestration for contextual salience adaptation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.cognitive.context.activity_log import ActivityLog
from app.cognitive.context.protocol import ContextProvider, SalienceRule
from app.cognitive.context.providers import (
    DailyActivityProvider,
    EmotionalSignalsProvider,
    RecentActivityProvider,
    RecurringBehaviorProvider,
    TimeOfDayProvider,
)
from app.cognitive.context.rules import (
    EmotionalThoughtRule,
    RecurringThemeRule,
    TriggerActivationRule,
    UnresolvedDurationRule,
)
from app.cognitive.context.types import (
    ContextRecalcResult,
    ContextState,
    ContextWindow,
    SalienceAdjustment,
    TriggerRule,
)
from app.models.schemas import ThoughtRead

DEFAULT_TRIGGER_RULES: tuple[TriggerRule, ...] = (
    TriggerRule(
        signal="activity:coding",
        window=ContextWindow.IMMEDIATE,
        content_patterns=("code", "coding", "program", "software", "debug", "rust", "python"),
        boost=0.15,
    ),
    TriggerRule(
        signal="time:night",
        window=ContextWindow.IMMEDIATE,
        content_patterns=("reflect", "review", "journal", "plan", "think"),
        boost=0.12,
    ),
    TriggerRule(
        signal="pattern:coding",
        window=ContextWindow.LONG_TERM,
        content_patterns=("code", "coding", "program", "software", "debug"),
        boost=0.1,
    ),
    TriggerRule(
        signal="daily:reflective",
        window=ContextWindow.DAILY,
        content_patterns=("reflect", "review", "journal", "plan"),
        boost=0.08,
    ),
)


@dataclass
class ContextEngineConfig:
    """Temporal bounds and limits for contextual salience recalculation."""

    immediate_minutes: float = 30.0
    daily_hours: float = 24.0
    long_term_days: float = 14.0
    max_adjustment: float = 0.25
    recurring_min_occurrences: int = 3


class ContextEngine:
    """Recalculate thought salience from pluggable contextual signals."""

    def __init__(
        self,
        activity_log: ActivityLog | None = None,
        providers: list[ContextProvider] | None = None,
        rules: list[SalienceRule] | None = None,
        config: ContextEngineConfig | None = None,
        trigger_rules: tuple[TriggerRule, ...] | None = None,
    ) -> None:
        """Initialize the context engine.

        Args:
            activity_log: Shared activity log for behavioral inference.
            providers: Context signal providers.
            rules: Salience adjustment rules.
            config: Temporal window configuration.
            trigger_rules: Trigger-based activation definitions.
        """
        self.activity_log = activity_log or ActivityLog()
        self.config = config or ContextEngineConfig()
        self.providers = providers or [
            TimeOfDayProvider(),
            RecentActivityProvider(),
            DailyActivityProvider(),
            RecurringBehaviorProvider(min_occurrences=self.config.recurring_min_occurrences),
            EmotionalSignalsProvider(),
        ]
        self.rules = rules or self.default_rules(trigger_rules or DEFAULT_TRIGGER_RULES)
        self._last_recalc_at: datetime | None = None

    @classmethod
    def default_providers(cls) -> list[ContextProvider]:
        """Return the default provider set.

        Returns:
            list[ContextProvider]: Built-in context providers.
        """
        return [
            TimeOfDayProvider(),
            RecentActivityProvider(),
            DailyActivityProvider(),
            RecurringBehaviorProvider(),
            EmotionalSignalsProvider(),
        ]

    @classmethod
    def default_rules(cls, trigger_rules: tuple[TriggerRule, ...]) -> list[SalienceRule]:
        """Return the default salience rule set.

        Args:
            trigger_rules: Trigger activation definitions.

        Returns:
            list[SalienceRule]: Built-in salience rules.
        """
        return [
            UnresolvedDurationRule(),
            EmotionalThoughtRule(),
            RecurringThemeRule(),
            TriggerActivationRule(list(trigger_rules)),
        ]

    def build_state(self, thoughts: list[ThoughtRead], now: datetime) -> ContextState:
        """Aggregate contextual signals across all windows.

        Args:
            thoughts: Active thoughts available to providers.
            now: Reference timestamp.

        Returns:
            ContextState: Aggregated contextual signals.
        """
        state = ContextState(now=now)
        window_bounds = {
            ContextWindow.IMMEDIATE: timedelta(minutes=self.config.immediate_minutes),
            ContextWindow.DAILY: timedelta(hours=self.config.daily_hours),
            ContextWindow.LONG_TERM: timedelta(days=self.config.long_term_days),
        }

        for provider in self.providers:
            since = now - window_bounds[provider.window]
            activities = self.activity_log.entries_since(since)
            signals = provider.collect(activities, thoughts, now)
            bucket = {
                ContextWindow.IMMEDIATE: state.immediate,
                ContextWindow.DAILY: state.daily,
                ContextWindow.LONG_TERM: state.long_term,
            }[provider.window]
            bucket.update(signals)

        if not any(key.startswith("time:") for key in state.immediate):
            clock = TimeOfDayProvider()
            state.immediate.update(clock.collect([], thoughts, now))

        return state

    def recalculate(
        self,
        thoughts: list[ThoughtRead],
        now: datetime | None = None,
    ) -> tuple[list[ThoughtRead], ContextRecalcResult]:
        """Recompute salience for thoughts using current context.

        Args:
            thoughts: Thoughts to adapt.
            now: Reference timestamp.

        Returns:
            tuple[list[ThoughtRead], ContextRecalcResult]: Updated thoughts and summary.
        """
        current_time = now or datetime.now()
        state = self.build_state(thoughts, current_time)
        result = ContextRecalcResult(
            active_signals={
                **{f"immediate:{key}": value for key, value in state.immediate.items()},
                **{f"daily:{key}": value for key, value in state.daily.items()},
                **{f"long_term:{key}": value for key, value in state.long_term.items()},
            },
        )

        updated: list[ThoughtRead] = []
        for thought in thoughts:
            total_delta = 0.0
            reasons: list[str] = []

            for rule in self.rules:
                delta, rule_reasons = rule.adjust(thought, state, self.activity_log.all_entries())
                if delta == 0.0:
                    continue
                total_delta += delta
                reasons.extend(rule_reasons)

            capped_delta = max(
                -self.config.max_adjustment,
                min(self.config.max_adjustment, total_delta),
            )
            new_salience = max(0.0, min(1.0, thought.salience + capped_delta))
            result.adjustments.append(
                SalienceAdjustment(
                    thought_id=thought.id,
                    delta=round(new_salience - thought.salience, 6),
                    reasons=reasons,
                )
            )

            if new_salience == thought.salience:
                updated.append(thought)
            else:
                updated.append(
                    thought.model_copy(
                        update={
                            "salience": new_salience,
                            "last_accessed": current_time,
                        },
                    )
                )

        self._last_recalc_at = current_time
        return updated, result

    def should_recalculate(self, now: datetime, interval_minutes: float) -> bool:
        """Return whether enough time has passed for another salience pass.

        Args:
            now: Reference timestamp.
            interval_minutes: Minimum minutes between recalculations.

        Returns:
            bool: True when recalculation should run.
        """
        if self._last_recalc_at is None:
            return True

        elapsed_minutes = (now - self._last_recalc_at).total_seconds() / 60.0
        return elapsed_minutes >= interval_minutes

    def reset_recalc_timer(self) -> None:
        """Allow the next tick to run contextual salience recalculation.

        Returns:
            None
        """
        self._last_recalc_at = None

    def register_provider(self, provider: ContextProvider) -> None:
        """Add a custom context provider.

        Args:
            provider: Provider to append.

        Returns:
            None
        """
        self.providers.append(provider)

    def register_rule(self, rule: SalienceRule) -> None:
        """Add a custom salience rule.

        Args:
            rule: Rule to append.

        Returns:
            None
        """
        self.rules.append(rule)

    def snapshot(self, thoughts: list[ThoughtRead], now: datetime | None = None) -> ContextState:
        """Return the current contextual state without changing salience.

        Args:
            thoughts: Active thoughts for provider inference.
            now: Reference timestamp.

        Returns:
            ContextState: Aggregated contextual signals.
        """
        return self.build_state(thoughts, now or datetime.now())
