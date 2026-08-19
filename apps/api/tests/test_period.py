"""Unit tests for the tz-aware period/week-bucketing helpers."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from devflow_api.core.services.period import (
    day_start_utc,
    is_sprint_start,
    local_date,
    resolve_tz,
    resolve_window,
    sprint_number,
    sprint_series,
    sprint_window,
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


# ---------------------------------------------------------------------------
# sprint_window
# ---------------------------------------------------------------------------


def test_sprint_window_no_anchor_falls_back_to_iso_week() -> None:
    # Wednesday Aug 19 2026 -> the ISO week is Mon Aug 17 - Mon Aug 24.
    at = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
    start, end = sprint_window(None, 14, at)
    assert start == datetime(2026, 8, 17, tzinfo=UTC)
    assert end == datetime(2026, 8, 24, tzinfo=UTC)


def test_sprint_window_on_anchor_day() -> None:
    anchor = date(2026, 8, 5)
    at = datetime(2026, 8, 5, 3, 0, tzinfo=UTC)
    start, end = sprint_window(anchor, 14, at)
    assert start == datetime(2026, 8, 5, tzinfo=UTC)
    assert end == datetime(2026, 8, 19, tzinfo=UTC)


def test_sprint_window_mid_sprint_after_anchor() -> None:
    anchor = date(2026, 8, 5)
    at = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)  # 7 days into the 14-day sprint
    start, end = sprint_window(anchor, 14, at)
    assert start == datetime(2026, 8, 5, tzinfo=UTC)
    assert end == datetime(2026, 8, 19, tzinfo=UTC)


def test_sprint_window_second_sprint_after_anchor() -> None:
    anchor = date(2026, 8, 5)
    at = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)  # 15 days in -> next sprint
    start, end = sprint_window(anchor, 14, at)
    assert start == datetime(2026, 8, 19, tzinfo=UTC)
    assert end == datetime(2026, 9, 2, tzinfo=UTC)


def test_sprint_window_before_anchor_lands_in_preceding_sprint() -> None:
    anchor = date(2026, 8, 5)
    at = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)  # 4 days before anchor
    start, end = sprint_window(anchor, 14, at)
    assert start == datetime(2026, 7, 22, tzinfo=UTC)
    assert end == datetime(2026, 8, 5, tzinfo=UTC)


def test_sprint_window_boundary_instant_belongs_to_next_sprint() -> None:
    anchor = date(2026, 8, 5)
    at = datetime(2026, 8, 19, 0, 0, tzinfo=UTC)  # exactly on the boundary
    start, end = sprint_window(anchor, 14, at)
    assert start == datetime(2026, 8, 19, tzinfo=UTC)
    assert end == datetime(2026, 9, 2, tzinfo=UTC)


def test_sprint_window_respects_timezone() -> None:
    anchor = date(2026, 8, 5)
    # 2026-08-19 00:30 UTC is already 2026-08-19 02:30 local in Warsaw
    # (CEST, UTC+2) -> falls on the boundary date, in the *next* sprint.
    at = datetime(2026, 8, 19, 0, 30, tzinfo=UTC)
    start, end = sprint_window(anchor, 14, at, WARSAW)
    assert start == datetime(2026, 8, 18, 22, 0, tzinfo=UTC)  # local Aug 19 00:00
    assert end == datetime(2026, 9, 1, 22, 0, tzinfo=UTC)  # local Sep 2 00:00


# ---------------------------------------------------------------------------
# sprint_number
# ---------------------------------------------------------------------------


def test_sprint_number_on_anchor_day_is_one() -> None:
    anchor = date(2026, 8, 5)
    assert sprint_number(anchor, 14, anchor) == 1


def test_sprint_number_second_sprint_is_two() -> None:
    anchor = date(2026, 8, 5)
    assert sprint_number(anchor, 14, date(2026, 8, 19)) == 2


def test_sprint_number_before_anchor_is_negative_or_zero() -> None:
    anchor = date(2026, 8, 5)
    # The sprint immediately preceding the anchor's is "sprint 0".
    assert sprint_number(anchor, 14, date(2026, 7, 22)) == 0


# ---------------------------------------------------------------------------
# is_sprint_start
# ---------------------------------------------------------------------------


def test_is_sprint_start_true_on_anchor_and_every_multiple() -> None:
    anchor = date(2026, 8, 5)
    assert is_sprint_start(anchor, 14, anchor) is True
    assert is_sprint_start(anchor, 14, date(2026, 8, 19)) is True
    assert is_sprint_start(anchor, 14, date(2026, 7, 22)) is True


def test_is_sprint_start_false_mid_sprint() -> None:
    anchor = date(2026, 8, 5)
    assert is_sprint_start(anchor, 14, date(2026, 8, 12)) is False
    assert is_sprint_start(anchor, 14, date(2026, 8, 6)) is False


def test_is_sprint_start_no_anchor_accepts_any_monday() -> None:
    # 2026-08-17 is a Monday.
    assert is_sprint_start(None, 14, date(2026, 8, 17)) is True
    assert is_sprint_start(None, 14, date(2026, 8, 18)) is False


# ---------------------------------------------------------------------------
# sprint_series
# ---------------------------------------------------------------------------


def test_sprint_series_length_and_order() -> None:
    anchor = date(2026, 8, 5)
    at = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)  # mid current sprint
    series = sprint_series(anchor, 14, at, back=2, forward=1)
    assert len(series) == 4
    assert [s.start for s in series] == [
        date(2026, 7, 8),
        date(2026, 7, 22),
        date(2026, 8, 5),
        date(2026, 8, 19),
    ]


def test_sprint_series_exactly_one_is_current() -> None:
    anchor = date(2026, 8, 5)
    at = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
    series = sprint_series(anchor, 14, at, back=3, forward=3)
    current = [s for s in series if s.is_current]
    assert len(current) == 1
    assert current[0].start == date(2026, 8, 5)
    assert current[0].end == date(2026, 8, 18)


def test_sprint_series_dates_are_contiguous() -> None:
    anchor = date(2026, 8, 5)
    at = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
    series = sprint_series(anchor, 14, at, back=2, forward=2)
    for earlier, later in zip(series, series[1:], strict=False):
        assert later.start == earlier.end + timedelta(days=1)


def test_sprint_series_numbers_increase_with_anchor() -> None:
    anchor = date(2026, 8, 5)
    at = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
    series = sprint_series(anchor, 14, at, back=1, forward=1)
    assert [s.number for s in series] == [0, 1, 2]


def test_sprint_series_respects_timezone() -> None:
    anchor = date(2026, 8, 5)
    # 00:30 UTC on the boundary date is already local Aug 19 in Warsaw.
    at = datetime(2026, 8, 19, 0, 30, tzinfo=UTC)
    series = sprint_series(anchor, 14, at, WARSAW, back=0, forward=0)
    assert series[0].start == date(2026, 8, 19)


def test_sprint_series_no_anchor_has_unnumbered_weekly_sprints() -> None:
    at = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)  # Wednesday
    series = sprint_series(None, 14, at, back=1, forward=1)
    assert all(s.number is None for s in series)
    assert [s.start for s in series] == [
        date(2026, 8, 10),
        date(2026, 8, 17),
        date(2026, 8, 24),
    ]
    assert series[1].end == date(2026, 8, 23)
