"""In-memory activity tracking for contextual inference."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta

from app.cognitive.context.types import ActivityRecord, ContextWindow
from app.cognitive.similarity import ThoughtSimilarity
from app.models.schemas import ThoughtCreate, ThoughtRead

DEFAULT_ACTIVITY_TAG_LEXICON: dict[str, tuple[str, ...]] = {
    "coding": ("code", "coding", "program", "software", "debug", "rust", "python", "typescript"),
    "reflective": ("reflect", "review", "journal", "plan", "think", "meditate"),
    "learning": ("learn", "study", "course", "read", "research"),
    "creative": ("design", "write", "draft", "create", "sketch"),
}


class ActivityLog:
    """Ring buffer of recent behavioral events."""

    def __init__(
        self,
        max_entries: int = 500,
        tag_lexicon: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        """Initialize the activity log.

        Args:
            max_entries: Maximum retained activity records.
            tag_lexicon: Token patterns used to infer activity tags.
        """
        self.max_entries = max_entries
        self.tag_lexicon = tag_lexicon or DEFAULT_ACTIVITY_TAG_LEXICON
        self._entries: deque[ActivityRecord] = deque(maxlen=max_entries)

    def record(
        self,
        activity_type: str,
        now: datetime,
        *,
        thought_id: str | None = None,
        content_hint: str = "",
        tags: tuple[str, ...] | None = None,
    ) -> ActivityRecord:
        """Append one activity record.

        Args:
            activity_type: Event classification.
            now: Event timestamp.
            thought_id: Related thought identifier.
            content_hint: Short text used for tag inference.
            tags: Optional explicit tags overriding inference.

        Returns:
            ActivityRecord: Stored activity record.
        """
        inferred = tags if tags is not None else self.infer_tags(content_hint, activity_type)
        entry = ActivityRecord(
            timestamp=now,
            activity_type=activity_type,
            tags=inferred,
            thought_id=thought_id,
            content_hint=content_hint[:200],
        )
        self._entries.appendleft(entry)
        return entry

    def record_thought(
        self,
        thought: ThoughtRead | ThoughtCreate,
        activity_type: str,
        now: datetime,
        *,
        thought_id: str | None = None,
    ) -> ActivityRecord:
        """Record an activity derived from a thought payload.

        Args:
            thought: Thought object or creation payload.
            activity_type: Event classification.
            now: Event timestamp.
            thought_id: Optional explicit thought id override.

        Returns:
            ActivityRecord: Stored activity record.
        """
        content = thought.content
        explicit_id = thought_id
        if explicit_id is None and hasattr(thought, "id"):
            explicit_id = getattr(thought, "id")
        return self.record(
            activity_type,
            now,
            thought_id=explicit_id,
            content_hint=content,
        )

    def infer_tags(self, content_hint: str, activity_type: str) -> tuple[str, ...]:
        """Infer activity tags from content and event type.

        Args:
            content_hint: Text snippet for lexical tagging.
            activity_type: Event classification.

        Returns:
            tuple[str, ...]: Inferred activity tags.
        """
        tokens = ThoughtSimilarity.tokenize(content_hint)
        tags: list[str] = []

        for tag, patterns in self.tag_lexicon.items():
            if any(pattern in tokens or pattern in content_hint.lower() for pattern in patterns):
                tags.append(tag)

        return tuple(sorted(set(tags)))

    def entries_since(self, since: datetime) -> list[ActivityRecord]:
        """Return activity records at or after a timestamp.

        Args:
            since: Lower bound timestamp.

        Returns:
            list[ActivityRecord]: Matching records oldest first.
        """
        records = [entry for entry in self._entries if entry.timestamp >= since]
        records.sort(key=lambda item: item.timestamp)
        return records

    def entries_for_window(self, window: ContextWindow, now: datetime) -> list[ActivityRecord]:
        """Return activity records for a context window.

        Args:
            window: Temporal scope to query.
            now: Reference timestamp.

        Returns:
            list[ActivityRecord]: Matching records oldest first.
        """
        delta = {
            ContextWindow.IMMEDIATE: timedelta(minutes=30),
            ContextWindow.DAILY: timedelta(hours=24),
            ContextWindow.LONG_TERM: timedelta(days=14),
        }[window]
        return self.entries_since(now - delta)

    def tag_counts(self, window: ContextWindow, now: datetime) -> dict[str, int]:
        """Count activity tags within a context window.

        Args:
            window: Temporal scope to query.
            now: Reference timestamp.

        Returns:
            dict[str, int]: Tag occurrence counts.
        """
        counts: dict[str, int] = {}
        for entry in self.entries_for_window(window, now):
            for tag in entry.tags:
                counts[tag] = counts.get(tag, 0) + 1
        return counts

    def all_entries(self) -> list[ActivityRecord]:
        """Return all retained activity records oldest first.

        Returns:
            list[ActivityRecord]: Stored records.
        """
        records = list(self._entries)
        records.sort(key=lambda item: item.timestamp)
        return records
