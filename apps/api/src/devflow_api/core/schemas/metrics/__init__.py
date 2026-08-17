"""Pydantic schemas for the Metrics module (productivity dashboards)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class MetricValueResponse(BaseModel):
    """A single metric value compared against the previous equal-length period."""

    value: float
    prev_value: float
    delta_pct: float | None


class SummaryResponse(BaseModel):
    period_from: datetime
    period_to: datetime
    tasks_completed: MetricValueResponse
    active_hours: MetricValueResponse


class WeeklyVelocityPointResponse(BaseModel):
    """Completed-task count for one ISO week (Monday-anchored, UTC)."""

    week_start: date
    tasks_completed: int


class VelocityResponse(BaseModel):
    period_from: datetime
    period_to: datetime
    total_done: int
    weeks: float = Field(description="Length of the period in weeks (>= 1.0).")
    average_per_week: float
    trend_pct: float | None
    weekly: list[WeeklyVelocityPointResponse]


class DailyHoursResponse(BaseModel):
    day: date
    hours: float


class TimeTrackingResponse(BaseModel):
    period_from: datetime
    period_to: datetime
    total_hours: float
    daily: list[DailyHoursResponse]


class CompletionRateResponse(BaseModel):
    period_from: datetime
    period_to: datetime
    done: int
    cancelled: int
    open: int
    completion_rate: float


class EstimationAccuracyResponse(BaseModel):
    period_from: datetime
    period_to: datetime
    sample_size: int
    average_ratio: float | None
    accurate_count: int
    over_estimated_count: int
    under_estimated_count: int


class StreakResponse(BaseModel):
    current_streak: int
    longest_streak: int


class ProjectMetricsResponse(BaseModel):
    project_id: uuid.UUID
    total_tasks: int
    open_tasks: int
    overdue_tasks: int
    overdue_rate: float
    health: str


class CycleTimeStageResponse(BaseModel):
    """Average dwell time in one status, from `task_status_changes`.

    Only counts transition pairs where the exit is a real recorded
    transition (see `MetricsService._compute_cycle_time` for why some pairs
    are excluded) — ``sample_size`` is how many such pairs contributed.
    """

    status: str
    average_hours: float
    sample_size: int


class StuckTaskResponse(BaseModel):
    """A task currently sitting in a non-terminal status the longest —
    the bottleneck-detection companion to `CycleTimeStageResponse`, which
    only reflects completed transitions."""

    task_id: uuid.UUID
    title: str
    status: str
    hours_in_status: float


class CycleTimeResponse(BaseModel):
    project_id: uuid.UUID
    stages: list[CycleTimeStageResponse]
    stuck: list[StuckTaskResponse]


class PRDashboardResponse(BaseModel):
    stale_pr_count: int
    time_to_first_review: float | None
    review_velocity: float | None
    weekly_throughput: int
    review_ratio: float | None


class PRDashboardMemberResponse(BaseModel):
    user_id: uuid.UUID
    display_name: str
    github_login: str | None


class PRDashboardMembersResponse(BaseModel):
    """Not paginated — `meta` is omitted per the documented envelope contract."""

    data: list[PRDashboardMemberResponse]


class PRTrendPointResponse(BaseModel):
    """One ISO week of PR flow for an organization (Monday-anchored, UTC).

    ``opened`` buckets by ``created_at_github``; ``merged`` buckets by
    ``merged_at`` (only PRs with ``state == "merged"``); ``avg_time_to_first_review_h``
    is a *cohort* reading — the average review-wait of PRs opened in this week
    (not reviewed in this week) — over PRs with a non-null ``first_review_at``.
    """

    week_start: date
    opened: int
    merged: int
    avg_time_to_first_review_h: float | None


class PRTrendsResponse(BaseModel):
    period_from: datetime
    period_to: datetime
    weekly: list[PRTrendPointResponse]


class PRBottleneckItemResponse(BaseModel):
    """One PR flagged as a bottleneck, identified well enough to act on
    without a second lookup (repo/owner is embedded in ``html_url``)."""

    number: int
    title: str
    author_login: str
    html_url: str


class StalePRBottleneckResponse(PRBottleneckItemResponse):
    age_days: float


class SlowReviewBottleneckResponse(PRBottleneckItemResponse):
    wait_hours: float


class PRFlowBottlenecksResponse(BaseModel):
    stale_open: list[StalePRBottleneckResponse]
    slowest_first_review: list[SlowReviewBottleneckResponse]


class MetricTrendPointResponse(BaseModel):
    """One ISO week's value for a metric (Monday-anchored, UTC).

    ``value: None`` means "computed, no sample that week" (e.g. no reviewed
    PR to average, no estimated+worked task) — distinct from a metric that
    legitimately counted zero, which stores ``0.0``. The most recent point
    covers the current, still-open week and is always computed live, never
    read from a persisted snapshot.
    """

    week_start: date
    value: float | None


class MetricTrendSeriesResponse(BaseModel):
    """Zero-filled series for one metric: exactly one point per week in the
    requested horizon, oldest first."""

    metric_key: str
    points: list[MetricTrendPointResponse]


class MetricTrendsResponse(BaseModel):
    period_from: datetime
    period_to: datetime
    weeks: int
    series: list[MetricTrendSeriesResponse]


class PRFlowReportResponse(BaseModel):
    """Payload shape for the ``pr_flow_weekly`` report type — the 5 PR-flow
    KPIs computed over an explicit period, plus the PRs actually driving
    them (audit gap #9: a weekly PR-flow report with named bottlenecks)."""

    period_from: datetime
    period_to: datetime
    stale_pr_count: int
    time_to_first_review_h: float | None
    review_velocity_h: float | None
    throughput: int
    review_ratio: float | None
    bottlenecks: PRFlowBottlenecksResponse
