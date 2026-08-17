"""Unit tests for the tz-aware period/week-bucketing helpers."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from devflow_api.core.services.period import (
    day_start_utc,
    local_date,
    resolve_tz,
    resolve_window,
    week_start,
)

WARSAW = ZoneInfo("Europe/Warsaw")


# ---------------------------------------------------------------------------
# resolve_tz
# ---------------------------------------------------------------------------


def test_resolve_tz_valid_name() -> None:
    assert resolve_tz("Europe/Warsaw") == WARSAW


def test_resolve_tz_none_falls_back_to_utc() -> None:
    assert resolve_tz(None) is UTC


def test_resolve_tz_garbage_falls_back_to_utc() -> None:
    assert resolve_tz("Mars/Phobos") is UTC


# ---------------------------------------------------------------------------
# local_date
# ---------------------------------------------------------------------------


def test_local_date_shifts_across_utc_midnight() -> None:
    # 23:30 UTC on Aug 16 is already 01:30 local on Aug 17 in Warsaw (CEST).
    moment = datetime(2026, 8, 16, 23, 30, tzinfo=UTC)
    assert local_date(moment, WARSAW) == date(2026, 8, 17)


def test_local_date_defaults_to_utc() -> None:
    moment = datetime(2026, 8, 16, 23, 30, tzinfo=UTC)
    assert local_date(moment) == date(2026, 8, 16)


# ---------------------------------------------------------------------------
# week_start
# ---------------------------------------------------------------------------


def test_week_start_sunday_evening_rolls_into_next_week_locally() -> None:
    # Sunday 23:00 UTC = Monday 01:00 CEST -> already the next ISO week
    # locally, even though it's still Sunday in UTC.
    sunday_late_utc = datetime(2026, 8, 16, 23, 0, tzinfo=UTC)  # Sunday
    assert week_start(sunday_late_utc) == date(2026, 8, 10)  # UTC: prior Monday
    # local: next Monday
    assert week_start(sunday_late_utc, WARSAW) == date(2026, 8, 17)


# ---------------------------------------------------------------------------
# day_start_utc
# ---------------------------------------------------------------------------


def test_day_start_utc_warsaw_summer_offset() -> None:
    # Europe/Warsaw is UTC+2 in August (CEST).
    assert day_start_utc(date(2026, 8, 17), WARSAW) == datetime(
        2026, 8, 16, 22, 0, tzinfo=UTC
    )


def test_day_start_utc_defaults_to_utc() -> None:
    assert day_start_utc(date(2026, 8, 17)) == datetime(2026, 8, 17, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# resolve_window
# ---------------------------------------------------------------------------


def test_resolve_window_date_only_includes_whole_local_day() -> None:
    start, end = resolve_window(date(2026, 7, 18), date(2026, 8, 17), WARSAW)
    assert start == datetime(2026, 7, 17, 22, 0, tzinfo=UTC)
    # end is local midnight of the day AFTER date_to, so Aug 17 local is
    # fully inside [start, end).
    assert end == datetime(2026, 8, 17, 22, 0, tzinfo=UTC)
    today_evening_local = datetime(2026, 8, 17, 20, 0, tzinfo=UTC)  # 22:00 CEST
    assert start <= today_evening_local < end


def test_resolve_window_datetime_is_treated_as_an_exact_instant() -> None:
    exact = datetime(2026, 8, 17, 6, 30, tzinfo=UTC)
    start, end = resolve_window(None, exact, WARSAW)
    assert end == exact


def test_resolve_window_defaults_when_both_omitted() -> None:
    start, end = resolve_window(None, None, UTC, default_days=30)
    assert (end - start).days == 30
