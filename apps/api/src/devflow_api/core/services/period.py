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

from dataclasses import dataclass
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


def effective_cadence(
    anchor: date | None, length_days: int, at: datetime, tz: tzinfo = UTC
) -> tuple[date, int]:
    """The ``(anchor, length_days)`` actually used to compute sprint boundaries.

    When ``anchor`` is ``None`` (no cadence configured for the org), falls
    back to the Monday of the ISO week containing *at*, with a fixed 7-day
    length — today's behaviour for every org that hasn't opted into sprint
    settings, regardless of what ``length_days`` happens to be set to.
    """
    if anchor is None:
        return week_start(at, tz), 7
    return anchor, length_days


def sprint_start_for(anchor: date, length_days: int, day: date) -> date:
    """The start date of the ``length_days``-long sprint (anchored at
    *anchor*) that contains *day*.

    ``anchor`` is the start date of *some* sprint (any one — past or future,
    doesn't matter which; the cadence is periodic so every sprint boundary
    can be derived from a single reference point).
    """
    offset_days = (day - anchor).days
    # Floor division so dates *before* the anchor land in the sprint that
    # precedes it, not get pulled forward into the anchor's own sprint.
    sprints_elapsed = offset_days // length_days
    return anchor + timedelta(days=sprints_elapsed * length_days)


def sprint_number(anchor: date, length_days: int, start: date) -> int:
    """1-based number of the sprint that starts on *start*, counting from
    the sprint that starts on *anchor* (sprint 1)."""
    return (start - anchor).days // length_days + 1


def is_sprint_start(anchor: date | None, length_days: int, day: date) -> bool:
    """Whether *day* is the first day of a sprint under this cadence.

    When ``anchor`` is ``None`` (fallback ISO-week cadence), any Monday is a
    valid boundary — the 7-day period divides the calendar evenly, so this
    doesn't need a reference instant the way ``effective_cadence`` does.
    """
    if anchor is None:
        return day.weekday() == 0
    return (day - anchor).days % length_days == 0


@dataclass(frozen=True)
class Sprint:
    """One sprint window, as inclusive calendar dates in the org's tz.

    ``number`` is 1-based, counting from the anchor, and is ``None`` when no
    cadence is configured — numbering relative to the floating ISO-week
    fallback wouldn't mean anything.
    """

    number: int | None
    start: date
    end: date
    is_current: bool


def sprint_series(
    anchor: date | None,
    length_days: int,
    at: datetime,
    tz: tzinfo = UTC,
    *,
    back: int,
    forward: int,
) -> list[Sprint]:
    """``back`` sprints before the current one, the current one, and
    ``forward`` sprints after it — oldest first.
    """
    eff_anchor, eff_length = effective_cadence(anchor, length_days, at, tz)
    current_start = sprint_start_for(eff_anchor, eff_length, local_date(at, tz))
    numbered = anchor is not None
    sprints = []
    for offset in range(-back, forward + 1):
        start = current_start + timedelta(days=offset * eff_length)
        sprints.append(
            Sprint(
                number=sprint_number(eff_anchor, eff_length, start)
                if numbered
                else None,
                start=start,
                end=start + timedelta(days=eff_length - 1),
                is_current=(offset == 0),
            )
        )
    return sprints


def sprint_window(
    anchor: date | None,
    length_days: int,
    at: datetime,
    tz: tzinfo = UTC,
) -> tuple[datetime, datetime]:
    """The ``[start, end)`` UTC instant window of the sprint containing *at*."""
    eff_anchor, eff_length = effective_cadence(anchor, length_days, at, tz)
    start_day = sprint_start_for(eff_anchor, eff_length, local_date(at, tz))
    end_day = start_day + timedelta(days=eff_length)
    return day_start_utc(start_day, tz), day_start_utc(end_day, tz)
