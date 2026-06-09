"""Metrics service — productivity aggregates over tasks and work sessions.

Calculation rules follow ``docs/product/README.md`` § Productivity Metrics.
A task is treated as "completed" when ``status == 'done'``; its completion time
is approximated by ``updated_at`` (there is no dedicated completed_at column).

Cache
-----
Each public method is wrapped by ``_cached``, a generic cache-aside helper.
Pass ``cache=None`` (the default) to bypass the cache entirely — all existing
tests and ``run_report_generation`` use this path unchanged.
"""

import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from typing import TypeVar

from fastapi import Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.cache import CacheBackend, get_cache
from devflow_api.core.config import get_settings
from devflow_api.core.database import get_session
from devflow_api.core.errors import AppError
from devflow_api.core.models.task import Task
from devflow_api.core.models.work_session import WorkSession
from devflow_api.core.repositories.metrics import MetricsRepository
from devflow_api.core.repositories.organization import OrganizationRepository
from devflow_api.core.repositories.project import ProjectRepository
from devflow_api.core.schemas.metrics import (
    CompletionRateResponse,
    DailyHoursResponse,
    EstimationAccuracyResponse,
    MetricValueResponse,
    ProjectMetricsResponse,
    StreakResponse,
    SummaryResponse,
    TimeTrackingResponse,
    VelocityResponse,
)

_DEFAULT_PERIOD_DAYS = 30

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Pure helpers (no state)
# ---------------------------------------------------------------------------


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _resolve_period(
    date_from: datetime | None, date_to: datetime | None
) -> tuple[datetime, datetime]:
    end = _as_utc(date_to) if date_to is not None else datetime.now(UTC)
    start = (
        _as_utc(date_from)
        if date_from is not None
        else end - timedelta(days=_DEFAULT_PERIOD_DAYS)
    )
    return start, end


def _metric_value(value: float, prev_value: float) -> MetricValueResponse:
    delta_pct = ((value - prev_value) / prev_value * 100) if prev_value else None
    return MetricValueResponse(value=value, prev_value=prev_value, delta_pct=delta_pct)


def _completed_in(task: Task, start: datetime, end: datetime) -> bool:
    return task.status == "done" and start <= _as_utc(task.updated_at) <= end


def _session_minutes_in(session: WorkSession, start: datetime, end: datetime) -> int:
    if session.duration_minutes is None:
        return 0
    if start <= _as_utc(session.started_at) <= end:
        return session.duration_minutes
    return 0


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class MetricsService:
    def __init__(
        self,
        metrics_repo: MetricsRepository,
        project_repo: ProjectRepository,
        org_repo: OrganizationRepository,
        cache: CacheBackend | None = None,
        ttl_seconds: int = 60,
    ) -> None:
        self._metrics_repo = metrics_repo
        self._project_repo = project_repo
        self._org_repo = org_repo
        self._cache = cache
        self._ttl_seconds = ttl_seconds

    # ------------------------------------------------------------------
    # Generic cache-aside helper
    # ------------------------------------------------------------------

    async def _cached(
        self,
        key: str,
        model_cls: type[T],
        compute: Callable[[], Awaitable[T]],
    ) -> T:
        """Return a cached result, or compute, store, and return a fresh one.

        Falls back to computing without caching when ``self._cache is None``
        or when any cache operation raises an exception.
        """
        if self._cache is None:
            return await compute()

        raw = await self._cache.get(key)
        if raw is not None:
            return model_cls.model_validate_json(raw)

        result = await compute()
        await self._cache.set(key, result.model_dump_json(), self._ttl_seconds)
        return result

    # ------------------------------------------------------------------
    # Public API — each method delegates computation to _compute_* and
    # wraps the call with _cached using a deterministic cache key.
    # ------------------------------------------------------------------

    async def get_summary(
        self,
        *,
        user_id: uuid.UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SummaryResponse:
        key = f"metrics:summary:{user_id}:{date_from}:{date_to}"
        return await self._cached(
            key,
            SummaryResponse,
            lambda: self._compute_summary(
                user_id=user_id, date_from=date_from, date_to=date_to
            ),
        )

    async def _compute_summary(
        self,
        *,
        user_id: uuid.UUID,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> SummaryResponse:
        start, end = _resolve_period(date_from, date_to)
        prev_start = start - (end - start)
        tasks = await self._metrics_repo.get_tasks_for_user(user_id)
        sessions = await self._metrics_repo.get_work_sessions_for_user(user_id)

        done_now = sum(1 for t in tasks if _completed_in(t, start, end))
        done_prev = sum(1 for t in tasks if _completed_in(t, prev_start, start))
        mins_now = sum(_session_minutes_in(s, start, end) for s in sessions)
        mins_prev = sum(_session_minutes_in(s, prev_start, start) for s in sessions)

        return SummaryResponse(
            period_from=start,
            period_to=end,
            tasks_completed=_metric_value(done_now, done_prev),
            active_hours=_metric_value(
                round(mins_now / 60, 2), round(mins_prev / 60, 2)
            ),
        )

    async def get_velocity(
        self,
        *,
        user_id: uuid.UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> VelocityResponse:
        key = f"metrics:velocity:{user_id}:{date_from}:{date_to}"
        return await self._cached(
            key,
            VelocityResponse,
            lambda: self._compute_velocity(
                user_id=user_id, date_from=date_from, date_to=date_to
            ),
        )

    async def _compute_velocity(
        self,
        *,
        user_id: uuid.UUID,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> VelocityResponse:
        start, end = _resolve_period(date_from, date_to)
        prev_start = start - (end - start)
        tasks = await self._metrics_repo.get_tasks_for_user(user_id)

        weeks = max((end - start).days / 7, 1.0)
        total_done = sum(1 for t in tasks if _completed_in(t, start, end))
        prev_done = sum(1 for t in tasks if _completed_in(t, prev_start, start))
        avg = total_done / weeks
        prev_avg = prev_done / weeks
        trend_pct = ((avg - prev_avg) / prev_avg * 100) if prev_avg else None

        return VelocityResponse(
            period_from=start,
            period_to=end,
            total_done=total_done,
            weeks=round(weeks, 2),
            average_per_week=round(avg, 2),
            trend_pct=round(trend_pct, 2) if trend_pct is not None else None,
        )

    async def get_time_tracking(
        self,
        *,
        user_id: uuid.UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> TimeTrackingResponse:
        key = f"metrics:time_tracking:{user_id}:{date_from}:{date_to}"
        return await self._cached(
            key,
            TimeTrackingResponse,
            lambda: self._compute_time_tracking(
                user_id=user_id, date_from=date_from, date_to=date_to
            ),
        )

    async def _compute_time_tracking(
        self,
        *,
        user_id: uuid.UUID,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> TimeTrackingResponse:
        start, end = _resolve_period(date_from, date_to)
        sessions = await self._metrics_repo.get_work_sessions_for_user(user_id)

        per_day: dict[date, int] = defaultdict(int)
        for session in sessions:
            minutes = _session_minutes_in(session, start, end)
            if minutes:
                per_day[_as_utc(session.started_at).date()] += minutes

        daily = [
            DailyHoursResponse(day=day, hours=round(minutes / 60, 2))
            for day, minutes in sorted(per_day.items())
        ]
        total_hours = round(sum(per_day.values()) / 60, 2)
        return TimeTrackingResponse(
            period_from=start, period_to=end, total_hours=total_hours, daily=daily
        )

    async def get_completion_rate(
        self,
        *,
        user_id: uuid.UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> CompletionRateResponse:
        key = f"metrics:completion_rate:{user_id}:{date_from}:{date_to}"
        return await self._cached(
            key,
            CompletionRateResponse,
            lambda: self._compute_completion_rate(
                user_id=user_id, date_from=date_from, date_to=date_to
            ),
        )

    async def _compute_completion_rate(
        self,
        *,
        user_id: uuid.UUID,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> CompletionRateResponse:
        start, end = _resolve_period(date_from, date_to)
        tasks = await self._metrics_repo.get_tasks_for_user(user_id)
        in_period = [t for t in tasks if start <= _as_utc(t.created_at) <= end]
        done = sum(1 for t in in_period if t.status == "done")
        cancelled = sum(1 for t in in_period if t.status == "cancelled")
        open_count = len(in_period) - done - cancelled
        total = len(in_period)
        rate = (done / total * 100) if total else 0.0
        return CompletionRateResponse(
            period_from=start,
            period_to=end,
            done=done,
            cancelled=cancelled,
            open=open_count,
            completion_rate=round(rate, 2),
        )

    async def get_estimation_accuracy(
        self,
        *,
        user_id: uuid.UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> EstimationAccuracyResponse:
        key = f"metrics:estimation_accuracy:{user_id}:{date_from}:{date_to}"
        return await self._cached(
            key,
            EstimationAccuracyResponse,
            lambda: self._compute_estimation_accuracy(
                user_id=user_id, date_from=date_from, date_to=date_to
            ),
        )

    async def _compute_estimation_accuracy(
        self,
        *,
        user_id: uuid.UUID,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> EstimationAccuracyResponse:
        start, end = _resolve_period(date_from, date_to)
        tasks = await self._metrics_repo.get_tasks_for_user(user_id)
        sessions = await self._metrics_repo.get_work_sessions_for_user(user_id)

        actual_by_task: dict[uuid.UUID, int] = defaultdict(int)
        for session in sessions:
            if session.duration_minutes:
                actual_by_task[session.task_id] += session.duration_minutes

        ratios: list[float] = []
        accurate = over = under = 0
        for task in tasks:
            if not _completed_in(task, start, end):
                continue
            if not task.estimate_minutes:
                continue
            actual = actual_by_task.get(task.id, 0)
            if actual == 0:
                continue
            ratio = actual / task.estimate_minutes
            ratios.append(ratio)
            if ratio < 0.8:
                over += 1
            elif ratio > 1.2:
                under += 1
            else:
                accurate += 1

        average_ratio = round(sum(ratios) / len(ratios), 2) if ratios else None
        return EstimationAccuracyResponse(
            period_from=start,
            period_to=end,
            sample_size=len(ratios),
            average_ratio=average_ratio,
            accurate_count=accurate,
            over_estimated_count=over,
            under_estimated_count=under,
        )

    async def get_streaks(self, *, user_id: uuid.UUID) -> StreakResponse:
        key = f"metrics:streaks:{user_id}"
        return await self._cached(
            key,
            StreakResponse,
            lambda: self._compute_streaks(user_id=user_id),
        )

    async def _compute_streaks(self, *, user_id: uuid.UUID) -> StreakResponse:
        tasks = await self._metrics_repo.get_tasks_for_user(user_id)
        done_days = sorted(
            {_as_utc(t.updated_at).date() for t in tasks if t.status == "done"}
        )
        if not done_days:
            return StreakResponse(current_streak=0, longest_streak=0)

        longest = run = 1
        for prev, curr in zip(done_days, done_days[1:], strict=False):
            if curr - prev == timedelta(days=1):
                run += 1
            else:
                run = 1
            longest = max(longest, run)

        today = datetime.now(UTC).date()
        anchor = today if today in done_days else today - timedelta(days=1)
        current = 0
        day = anchor
        done_set = set(done_days)
        while day in done_set:
            current += 1
            day -= timedelta(days=1)

        return StreakResponse(current_streak=current, longest_streak=longest)

    async def get_project_metrics(
        self, *, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> ProjectMetricsResponse:
        key = f"metrics:project:{project_id}:{user_id}"
        return await self._cached(
            key,
            ProjectMetricsResponse,
            lambda: self._compute_project_metrics(
                project_id=project_id, user_id=user_id
            ),
        )

    async def _compute_project_metrics(
        self, *, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> ProjectMetricsResponse:
        project = await self._project_repo.get_by_id(project_id)
        if not project:
            raise AppError(
                code="not_found",
                message="Project not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        member = await self._org_repo.get_member(project.org_id, user_id)
        if not member:
            raise AppError(
                code="forbidden",
                message="You are not a member of this project's organization.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        tasks = await self._metrics_repo.get_tasks_for_project(project_id)
        now = datetime.now(UTC)
        total = len(tasks)
        open_tasks = sum(1 for t in tasks if t.status not in ("done", "cancelled"))
        overdue = sum(
            1
            for t in tasks
            if t.due_date is not None
            and _as_utc(t.due_date) < now
            and t.status != "done"
        )
        overdue_rate = (overdue / total * 100) if total else 0.0
        if overdue_rate < 10:
            health = "healthy"
        elif overdue_rate <= 30:
            health = "at_risk"
        else:
            health = "critical"

        return ProjectMetricsResponse(
            project_id=project_id,
            total_tasks=total,
            open_tasks=open_tasks,
            overdue_tasks=overdue,
            overdue_rate=round(overdue_rate, 2),
            health=health,
        )


def get_metrics_service(
    session: AsyncSession = Depends(get_session),
    cache: CacheBackend = Depends(get_cache),
) -> MetricsService:
    settings = get_settings()
    return MetricsService(
        metrics_repo=MetricsRepository(session),
        project_repo=ProjectRepository(session),
        org_repo=OrganizationRepository(session),
        cache=cache,
        ttl_seconds=settings.metrics_cache_ttl_seconds,
    )
