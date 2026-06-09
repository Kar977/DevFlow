"""Pydantic schemas for the Metrics module (productivity dashboards)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


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


class VelocityResponse(BaseModel):
    period_from: datetime
    period_to: datetime
    total_done: int
    weeks: float
    average_per_week: float
    trend_pct: float | None


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
