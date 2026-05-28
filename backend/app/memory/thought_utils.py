"""Shared helpers for thought lifecycle logic."""

from datetime import datetime

from app.models.schemas import ThoughtRead


def is_active_thought(thought: ThoughtRead, now: datetime) -> bool:
    """Check whether a thought is unresolved and not expired.

    Args:
        thought: Thought to evaluate.
        now: Reference time for expiry comparison.

    Returns:
        bool: True when the thought is active.
    """
    if thought.resolved:
        return False
    if thought.expires_at is not None and thought.expires_at <= now:
        return False
    return True


def apply_salience_decay(
    thought: ThoughtRead,
    now: datetime,
    decay_rate_per_hour: float,
) -> ThoughtRead:
    """Apply linear salience decay based on time since last access.

    Args:
        thought: Thought to decay.
        now: Reference time for decay calculation.
        decay_rate_per_hour: Salience subtracted per elapsed hour.

    Returns:
        ThoughtRead: Thought with updated salience and last_accessed.
    """
    elapsed_hours = (now - thought.last_accessed).total_seconds() / 3600.0
    if elapsed_hours <= 0:
        return thought.model_copy(deep=True)

    decayed_salience = max(0.0, thought.salience - (decay_rate_per_hour * elapsed_hours))
    return thought.model_copy(
        update={
            "salience": decayed_salience,
            "last_accessed": now,
        },
        deep=True,
    )
