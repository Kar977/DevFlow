"""Time anchors and date-generation helpers for the demo dataset.

Every date the seeder writes is computed relative to ``now`` — captured once,
at the top of a seed run — never hardcoded. That is what makes the dataset
look equally fresh whether the container was started today or six months
ago (see ``entrypoint.sh``, which reseeds on every start).

Day-boundary rule: any timestamp whose *calendar day* matters for a metric
(``tasks.completed_at``, ``work_sessions.started_at``) is placed between
08:00 and 18:00 UTC via :meth:`Timeline.daytime`. Europe/Warsaw is UTC+1/+2,
so that window never crosses into a neighbouring local day — streaks, daily
hour totals and week buckets come out identical whether read in UTC or in
the demo users' local timezone.
"""

import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from devflow_api.core.services.period import sprint_start_for, week_start

SPRINT_LENGTH_DAYS = 14
STALE_PR_THRESHOLD_DAYS = 5
DEMO_TIMEZONE = "Europe/Warsaw"
HORIZON_WEEKS = 53

# Anchor a whole number of sprints before "today", so the current sprint
# always starts exactly on the current Monday.
_SPRINT_ANCHOR_LOOKBACK_SPRINTS = 13

# Mon..Sun weights for "when in a week does new work tend to land" — heavily
# weekday-biased, matching a real team's rhythm.
_WEEKDAY_WEIGHTS = (3, 3, 3, 3, 3, 1, 1)


@dataclass(frozen=True)
class Timeline:
    """The fixed instant a seed run treats as "now", plus derived anchors."""

    now: datetime
    current_monday: date
    sprint_anchor: date

    @classmethod
    def capture(cls) -> Timeline:
        """Snapshot the real "now" and derive the current week / sprint anchors."""
        return cls.at(datetime.now(UTC))

    @classmethod
    def at(cls, now: datetime) -> Timeline:
        """Derive the current week / sprint anchors for a given "now".

        Exposed separately from :meth:`capture` so tests (and an end-to-end
        reseed test fixing "now" to a known instant) don't have to wait on
        the wall clock or capture it twice.
        """
        monday = week_start(now)
        lookback_days = _SPRINT_ANCHOR_LOOKBACK_SPRINTS * SPRINT_LENGTH_DAYS
        anchor = monday - timedelta(days=lookback_days)
        return cls(now=now, current_monday=monday, sprint_anchor=anchor)

    def daytime(
        self,
        day: date,
        rng: random.Random,
        *,
        early_hour: int = 8,
        late_hour: int = 18,
    ) -> datetime:
        """A timestamp on *day*, drawn uniformly between the given UTC hours.

        Clamped to never exceed "now" — a no-op for any *day* strictly
        before today, but load-bearing when *day* is today: an hour drawn
        from the usual 08:00-18:00 window can otherwise land after the
        actual current time, producing a created-in-the-future row (see
        the regression this guards against in ``creation_dates_over_weeks``,
        which clamps the *day* but not the *hour*).
        """
        offset = timedelta(seconds=rng.uniform(early_hour * 3600, late_hour * 3600))
        moment = datetime.combine(day, datetime.min.time(), tzinfo=UTC) + offset
        return min(moment, self.now)

    def days_ago(self, n: int) -> date:
        """The calendar date *n* days before "now"."""
        return (self.now - timedelta(days=n)).date()

    def sprint_start_on_or_before(self, day: date) -> date:
        """The start date of the sprint (under the demo cadence) containing *day*."""
        return sprint_start_for(self.sprint_anchor, SPRINT_LENGTH_DAYS, day)


def weekday_biased_offset(rng: random.Random) -> int:
    """A day-of-week offset (0=Monday..6=Sunday), weighted toward weekdays."""
    return rng.choices(range(7), weights=_WEEKDAY_WEIGHTS, k=1)[0]


def creation_dates_over_weeks(
    rng: random.Random,
    timeline: Timeline,
    *,
    weeks: int,
    recent_weeks: int,
    recent_per_week: tuple[int, int],
    older_per_week: tuple[int, int],
) -> list[date]:
    """Weekday-biased creation dates spread across the last *weeks* weeks.

    Week 0 is the current week (``timeline.current_monday``); higher indices
    go further back. The first *recent_weeks* weeks draw a count per week
    from ``recent_per_week``, the rest from the (lower) ``older_per_week`` —
    this is what makes a velocity/throughput chart denser in the recent past
    and taper off further back, instead of a flat line.

    Every date is clamped to ``timeline.now``'s calendar day — without this,
    week 0's weekday-biased offset could land later in the current week than
    "today" (e.g. "Thursday" while today is Monday), producing a
    created-in-the-future row. Downstream that turns into a *negative*
    review-wait or dwell time the moment anything is computed relative to
    "now", corrupting an average silently rather than raising.
    """
    today = timeline.now.date()
    dates: list[date] = []
    for week_index in range(weeks):
        monday = timeline.current_monday - timedelta(days=7 * week_index)
        lo, hi = recent_per_week if week_index < recent_weeks else older_per_week
        for _ in range(rng.randint(lo, hi)):
            day = monday + timedelta(days=weekday_biased_offset(rng))
            dates.append(min(day, today))
    return dates
