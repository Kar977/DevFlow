"""Shared period/week-bucketing helpers for metrics-style services.

Extracted from ``MetricsService`` (where ``_week_start`` originated) after
``PRMetricsService`` grew an identical copy — both compute Monday-anchored
ISO weeks in UTC, and ``MetricSnapshotService`` needs the same definition to
decide which weeks are "closed" and therefore safe to persist.

Every function here defaults its ``tz`` parameter to UTC, so existing call
sites that don't pass one keep exactly the behaviour they had before
timezone support was added — the shift to a user's local time is opt-in per
call, not a global behaviour change.
"""

from datetime import UTC, date, datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def as_utc(value: datetime) -> datetime:
    """Attach UTC if *value* is naive; leave aware values unchanged."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def resolve_tz(name: str | None) -> tzinfo:
    """IANA zone name -> tzinfo, defaulting to UTC.

    ``None`` (timezone never set) and an unrecognized/garbage name are
    treated identically: fall back to UTC rather than raise. A bad value
    stored on a user row must degrade the dashboard's bucketing, never 500
    it — validation of the *input* happens once, at the point it's written
    (``UpdateProfileRequest``), not on every read.
    """
    if name is None:
        return UTC
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError, ValueError:
        return UTC


def local_date(moment: datetime, tz: tzinfo = UTC) -> date:
    """The calendar date *moment* falls on, viewed from *tz*."""
    return as_utc(moment).astimezone(tz).date()


def week_start(moment: datetime, tz: tzinfo = UTC) -> date:
    """Monday of the ISO week containing *moment*, viewed from *tz*."""
    day = local_date(moment, tz)
    return day - timedelta(days=day.weekday())


def day_start_utc(day: date, tz: tzinfo = UTC) -> datetime:
    """Local midnight of *day* in *tz*, as an aware UTC instant.

    Every real IANA zone has a local 00:00 (transitions land later in the
    day), so this is always well-defined; it's the standard
    ``datetime.combine(...).astimezone(UTC)`` trick.
    """
    local_midnight = datetime.combine(day, datetime.min.time(), tzinfo=tz)
    return local_midnight.astimezone(UTC)


def _to_instant(value: date, tz: tzinfo, *, exclusive_end: bool) -> datetime:
    """Coerce a ``date | datetime`` window endpoint to an aware UTC instant.

    ``datetime`` is a subclass of ``date``, so callers type this as
    ``date | None`` (a wider ``date | datetime`` collapses to ``date`` under
    mypy) — which means the ``isinstance(value, datetime)`` check below MUST
    run before any ``date``-only handling, or a ``datetime`` gets silently
    truncated to its date.

    A bare ``date`` means "a whole local calendar day": for the window's
    end that's local midnight of the day *after* it, so the day itself is
    fully included — this is what makes "today" show up in a `date_to`
    window instead of being cut off at its own midnight.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=tz)
    day = value + timedelta(days=1) if exclusive_end else value
    return day_start_utc(day, tz)


def resolve_window(
    date_from: date | None,
    date_to: date | None,
    tz: tzinfo,
    default_days: int = 30,
) -> tuple[datetime, datetime]:
    """Resolve a metrics query window to a half-open ``[start, end)`` in UTC.

    A bare ``date`` is a local calendar day; ``date_to`` in particular ends
    at local midnight of the *following* day, so the day it names is fully
    inside the window. When both are omitted, the window is the last
    ``default_days`` days ending "now" — unchanged from before timezones
    were tracked.
    """
    end = (
        _to_instant(date_to, tz, exclusive_end=True)
        if date_to is not None
        else datetime.now(UTC)
    )
    start = (
        _to_instant(date_from, tz, exclusive_end=False)
        if date_from is not None
        else end - timedelta(days=default_days)
    )
    return start, end
