"""Shared period/week-bucketing helpers for metrics-style services.

Extracted from ``MetricsService`` (where ``_week_start`` originated) after
``PRMetricsService`` grew an identical copy — both compute Monday-anchored
ISO weeks in UTC, and ``MetricSnapshotService`` needs the same definition to
decide which weeks are "closed" and therefore safe to persist.
"""

from datetime import UTC, date, datetime, timedelta


def as_utc(value: datetime) -> datetime:
    """Attach UTC if *value* is naive; leave aware values unchanged."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def week_start(moment: datetime) -> date:
    """Monday of the ISO week containing *moment*, in UTC."""
    day = as_utc(moment).date()
    return day - timedelta(days=day.weekday())
