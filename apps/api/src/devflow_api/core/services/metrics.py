"""Metrics service — productivity aggregates over tasks and work sessions.

Calculation rules follow ``docs/product/README.md`` § Productivity Metrics.
A task is treated as "completed" when ``status == 'done'``; its completion time
is ``Task.completed_at`` (set once by ``TaskService.update_task`` on the
``-> done`` transition), falling back to ``updated_at`` for rows written
before that column existed.

Cache
-----
Each public method is wrapped by ``_cached``, a generic cache-aside helper.
Pass ``cache=None`` (the default) to bypass the cache entirely — all existing
tests and ``run_report_generation`` use this path unchanged.
"""

import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta, tzinfo
from typing import TypeVar

from fastapi import Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.cache import CacheBackend, get_cache
from devflow_api.core.config import get_settings
from devflow_api.core.database import get_session
from devflow_api.core.errors import AppError
from devflow_api.core.models.task import OVERDUE_EXCLUDED_STATUSES, Task
from devflow_api.core.models.task_status_change import TaskStatusChange
from devflow_api.core.models.work_session import WorkSession
from devflow_api.core.repositories.metrics import MetricsRepository
from devflow_api.core.repositories.organization import OrganizationRepository
from devflow_api.core.repositories.project import ProjectRepository
from devflow_api.core.repositories.task_status_change import (
    TaskStatusChangeRepository,
)
from devflow_api.core.repositories.user import UserRepository
from devflow_api.core.schemas.metrics import (
    CompletionRateResponse,
    CycleTimeResponse,
    CycleTimeStageResponse,
    DailyHoursResponse,
    EstimationAccuracyResponse,
    MetricValueResponse,
    ProjectMetricsResponse,
    StreakResponse,
    StuckTaskResponse,
    SummaryResponse,
    TimeTrackingResponse,
    VelocityResponse,
    WeeklyVelocityPointResponse,
)
from devflow_api.core.services.cache_aside import cached
from devflow_api.core.services.org_access import resolve_metrics_subject
from devflow_api.core.services.period import as_utc as _as_utc
from devflow_api.core.services.period import local_date as _local_date
from devflow_api.core.services.period import resolve_tz as _resolve_tz
from devflow_api.core.services.period import resolve_window as _resolve_window
from devflow_api.core.services.period import week_start as _week_start

_DEFAULT_PERIOD_DAYS = 30

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Pure helpers (no state)
# ---------------------------------------------------------------------------


# Canonical workflow order for cycle-time stages — matches the frontend's
# `TASK_STATUS_LABELS` ordering. Any status value not in this tuple (there's
# no DB-level enum constraint on Task.status) sorts to the end.
_STAGE_ORDER = ("backlog", "todo", "in_progress", "review", "done", "cancelled")


def _stage_sort_key(status_value: str) -> int:
    return (
        _STAGE_ORDER.index(status_value)
        if status_value in _STAGE_ORDER
        else len(_STAGE_ORDER)
    )


def _metric_value(value: float, prev_value: float) -> MetricValueResponse:
    delta_pct = ((value - prev_value) / prev_value * 100) if prev_value else None
    return MetricValueResponse(value=value, prev_value=prev_value, delta_pct=delta_pct)


def _completion_time(task: Task) -> datetime:
    """Completion instant: the real column, falling back to updated_at for
    rows written before completed_at existed (or set outside the service)."""
    return _as_utc(task.completed_at or task.updated_at)


def _completed_in(task: Task, start: datetime, end: datetime) -> bool:
    """Half-open ``[start, end)`` — a task can't land in two adjacent windows."""
    return task.status == "done" and start <= _completion_time(task) < end


def _session_minutes_in(session: WorkSession, start: datetime, end: datetime) -> float:
    if session.duration_seconds is None:
        return 0
    if start <= _as_utc(session.started_at) < end:
        return session.duration_seconds / 60
    return 0


def _compute_cycle_time(
    tasks: list[Task],
    changes_by_task: dict[uuid.UUID, list[TaskStatusChange]],
    now: datetime,
) -> tuple[list[CycleTimeStageResponse], list[StuckTaskResponse]]:
    """Average dwell time per status, plus the tasks stuck longest right now.

    Each task's rows (already ordered oldest-first by
    ``TaskStatusChangeRepository.list_for_tasks``) form a timeline:
    consecutive rows ``(entry, exit)`` mean the task spent
    ``exit.changed_at - entry.changed_at`` in ``entry.to_status``.

    One kind of pair is systematically excluded: where ``exit.changed_by is
    None``. That's the unique fingerprint of migration 0017's synthetic
    "-> done" backfill row, written for tasks completed before status
    history existed — every real transition ``TaskService`` writes always
    carries a ``changed_by``. For a task that passed through real
    intermediate statuses *before* the migration shipped, only two
    backfilled rows exist for it (the "backlog" creation row and this
    "done" row), so the gap between them isn't really "time in backlog" —
    it's the task's entire pre-migration lifetime. Excluding pairs that end
    in a ``changed_by is None`` row drops exactly that corrupted
    measurement without touching any real data.

    The "stuck" list has no such caveat: it measures time since each
    non-terminal task's *last known* transition, which is accurate whether
    that row was backfilled or not.
    """
    durations_by_status: dict[str, list[float]] = defaultdict(list)
    stuck: list[StuckTaskResponse] = []
    tasks_by_id = {t.id: t for t in tasks}

    for task_id, rows in changes_by_task.items():
        for entry, exit_row in zip(rows, rows[1:], strict=False):
            if exit_row.changed_by is None:
                continue
            hours = (
                _as_utc(exit_row.changed_at) - _as_utc(entry.changed_at)
            ).total_seconds() / 3600
            durations_by_status[entry.to_status].append(hours)

        task = tasks_by_id.get(task_id)
        if task is None or not rows or task.status in ("done", "cancelled"):
            continue
        last = rows[-1]
        stuck.append(
            StuckTaskResponse(
                task_id=task_id,
                title=task.title,
                status=last.to_status,
                hours_in_status=round(
                    (now - _as_utc(last.changed_at)).total_seconds() / 3600, 2
                ),
            )
        )

    stages = sorted(
        (
            CycleTimeStageResponse(
                status=status_value,
                average_hours=round(sum(durs) / len(durs), 2),
                sample_size=len(durs),
            )
            for status_value, durs in durations_by_status.items()
        ),
        key=lambda s: _stage_sort_key(s.status),
    )
    stuck.sort(key=lambda s: s.hours_in_status, reverse=True)
    return stages, stuck[:5]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class MetricsService:
    def __init__(
        self,
        metrics_repo: MetricsRepository,
        project_repo: ProjectRepository,
        org_repo: OrganizationRepository,
        user_repo: UserRepository,
        status_change_repo: TaskStatusChangeRepository,
        cache: CacheBackend | None = None,
        ttl_seconds: int = 60,
    ) -> None:
        self._metrics_repo = metrics_repo
        self._project_repo = project_repo
        self._org_repo = org_repo
        self._user_repo = user_repo
        self._status_change_repo = status_change_repo
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

        Delegates to the shared :func:`cache_aside.cached` helper — kept as a
        thin instance method so existing call sites (``self._cached(...)``)
        stay unchanged.
        """
        return await cached(self._cache, key, model_cls, self._ttl_seconds, compute)

    async def _user_tz(self, user_id: uuid.UUID) -> tzinfo:
        """Resolve the user's stored IANA zone, defaulting to UTC.

        Called before every ``_cached(...)`` so the resolved zone name can be
        folded into the cache key — a timezone change then self-heals
        immediately instead of serving another zone's numbers for up to the
        cache TTL.
        """
        user = await self._user_repo.get_by_id(user_id)
        return _resolve_tz(user.timezone if user is not None else None)

    # ------------------------------------------------------------------
    # Public API — each method delegates computation to _compute_* and
    # wraps the call with _cached using a deterministic cache key.
    # ------------------------------------------------------------------

    async def get_summary(
        self,
        *,
        user_id: uuid.UUID,
        date_from: date | None = None,
        date_to: date | None = None,
        organization_id: uuid.UUID | None = None,
        member_user_id: uuid.UUID | None = None,
    ) -> SummaryResponse:
        # Authorization must never be served from cache.
        subject_id = await resolve_metrics_subject(
            self._org_repo,
            caller_id=user_id,
            organization_id=organization_id,
            member_user_id=member_user_id,
        )
        tz = await self._user_tz(subject_id)
        # "v2": key now carries the resolved zone name, so a timezone change
        # self-heals immediately instead of serving stale numbers for the
        # TTL — see _user_tz.
        key = f"metrics:summary:v2:{subject_id}:{tz}:{date_from}:{date_to}"
        return await self._cached(
            key,
            SummaryResponse,
            lambda: self._compute_summary(
                user_id=subject_id, date_from=date_from, date_to=date_to, tz=tz
            ),
        )

    async def _compute_summary(
        self,
        *,
        user_id: uuid.UUID,
        date_from: date | None,
        date_to: date | None,
        tz: tzinfo,
    ) -> SummaryResponse:
        start, end = _resolve_window(date_from, date_to, tz, _DEFAULT_PERIOD_DAYS)
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
        date_from: date | None = None,
        date_to: date | None = None,
        organization_id: uuid.UUID | None = None,
        member_user_id: uuid.UUID | None = None,
    ) -> VelocityResponse:
        subject_id = await resolve_metrics_subject(
            self._org_repo,
            caller_id=user_id,
            organization_id=organization_id,
            member_user_id=member_user_id,
        )
        # Cache key is versioned ("v3": v2 added `weekly`, v3 adds the tz
        # name) because an incompatible blob from an older key format would
        # fail validation on read and 500 for up to the cache TTL.
        tz = await self._user_tz(subject_id)
        key = f"metrics:velocity:v3:{subject_id}:{tz}:{date_from}:{date_to}"
        return await self._cached(
            key,
            VelocityResponse,
            lambda: self._compute_velocity(
                user_id=subject_id, date_from=date_from, date_to=date_to, tz=tz
            ),
        )

    async def _compute_velocity(
        self,
        *,
        user_id: uuid.UUID,
        date_from: date | None,
        date_to: date | None,
        tz: tzinfo,
    ) -> VelocityResponse:
        start, end = _resolve_window(date_from, date_to, tz, _DEFAULT_PERIOD_DAYS)
        prev_start = start - (end - start)
        tasks = await self._metrics_repo.get_tasks_for_user(user_id)

        weeks = max((end - start) / timedelta(weeks=1), 1.0)
        total_done = sum(1 for t in tasks if _completed_in(t, start, end))
        prev_done = sum(1 for t in tasks if _completed_in(t, prev_start, start))
        avg = total_done / weeks
        prev_avg = prev_done / weeks
        trend_pct = ((avg - prev_avg) / prev_avg * 100) if prev_avg else None

        # Zero-filled weekly buckets: a sparse series would lie about the
        # x-axis on a chart, so every ISO week in [start, end) gets an
        # entry. `end` is exclusive, so the last bucket is the week
        # containing the instant just before it — using `end` itself would
        # add a spurious trailing empty week whenever it lands exactly on a
        # Monday.
        buckets: dict[date, int] = {}
        cursor = _week_start(start, tz)
        last = _week_start(end - timedelta(microseconds=1), tz)
        while cursor <= last:
            buckets[cursor] = 0
            cursor += timedelta(days=7)
        for task in tasks:
            if _completed_in(task, start, end):
                bucket = _week_start(_completion_time(task), tz)
                if bucket in buckets:
                    buckets[bucket] += 1
        weekly = [
            WeeklyVelocityPointResponse(week_start=day, tasks_completed=count)
            for day, count in sorted(buckets.items())
        ]

        return VelocityResponse(
            period_from=start,
            period_to=end,
            total_done=total_done,
            weeks=round(weeks, 2),
            average_per_week=round(avg, 2),
            trend_pct=round(trend_pct, 2) if trend_pct is not None else None,
            weekly=weekly,
        )

    async def get_time_tracking(
        self,
        *,
        user_id: uuid.UUID,
        date_from: date | None = None,
        date_to: date | None = None,
        organization_id: uuid.UUID | None = None,
        member_user_id: uuid.UUID | None = None,
    ) -> TimeTrackingResponse:
        subject_id = await resolve_metrics_subject(
            self._org_repo,
            caller_id=user_id,
            organization_id=organization_id,
            member_user_id=member_user_id,
        )
        tz = await self._user_tz(subject_id)
        key = f"metrics:time_tracking:v2:{subject_id}:{tz}:{date_from}:{date_to}"
        return await self._cached(
            key,
            TimeTrackingResponse,
            lambda: self._compute_time_tracking(
                user_id=subject_id, date_from=date_from, date_to=date_to, tz=tz
            ),
        )

    async def _compute_time_tracking(
        self,
        *,
        user_id: uuid.UUID,
        date_from: date | None,
        date_to: date | None,
        tz: tzinfo,
    ) -> TimeTrackingResponse:
        start, end = _resolve_window(date_from, date_to, tz, _DEFAULT_PERIOD_DAYS)
        sessions = await self._metrics_repo.get_work_sessions_for_user(user_id)

        per_day: dict[date, float] = defaultdict(float)
        for session in sessions:
            minutes = _session_minutes_in(session, start, end)
            if minutes:
                per_day[_local_date(session.started_at, tz)] += minutes

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
        date_from: date | None = None,
        date_to: date | None = None,
        organization_id: uuid.UUID | None = None,
        member_user_id: uuid.UUID | None = None,
    ) -> CompletionRateResponse:
        subject_id = await resolve_metrics_subject(
            self._org_repo,
            caller_id=user_id,
            organization_id=organization_id,
            member_user_id=member_user_id,
        )
        tz = await self._user_tz(subject_id)
        key = f"metrics:completion_rate:v2:{subject_id}:{tz}:{date_from}:{date_to}"
        return await self._cached(
            key,
            CompletionRateResponse,
            lambda: self._compute_completion_rate(
                user_id=subject_id, date_from=date_from, date_to=date_to, tz=tz
            ),
        )

    async def _compute_completion_rate(
        self,
        *,
        user_id: uuid.UUID,
        date_from: date | None,
        date_to: date | None,
        tz: tzinfo,
    ) -> CompletionRateResponse:
        start, end = _resolve_window(date_from, date_to, tz, _DEFAULT_PERIOD_DAYS)
        tasks = await self._metrics_repo.get_tasks_for_user(user_id)
        in_period = [t for t in tasks if start <= _as_utc(t.created_at) < end]
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
        date_from: date | None = None,
        date_to: date | None = None,
        organization_id: uuid.UUID | None = None,
        member_user_id: uuid.UUID | None = None,
    ) -> EstimationAccuracyResponse:
        subject_id = await resolve_metrics_subject(
            self._org_repo,
            caller_id=user_id,
            organization_id=organization_id,
            member_user_id=member_user_id,
        )
        tz = await self._user_tz(subject_id)
        key = f"metrics:estimation_accuracy:v2:{subject_id}:{tz}:{date_from}:{date_to}"
        return await self._cached(
            key,
            EstimationAccuracyResponse,
            lambda: self._compute_estimation_accuracy(
                user_id=subject_id, date_from=date_from, date_to=date_to, tz=tz
            ),
        )

    async def _compute_estimation_accuracy(
        self,
        *,
        user_id: uuid.UUID,
        date_from: date | None,
        date_to: date | None,
        tz: tzinfo,
    ) -> EstimationAccuracyResponse:
        start, end = _resolve_window(date_from, date_to, tz, _DEFAULT_PERIOD_DAYS)
        tasks = await self._metrics_repo.get_tasks_for_user(user_id)
        sessions = await self._metrics_repo.get_work_sessions_for_user(user_id)

        actual_by_task: dict[uuid.UUID, float] = defaultdict(float)
        for session in sessions:
            if session.duration_seconds:
                actual_by_task[session.task_id] += session.duration_seconds / 60

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

    async def get_streaks(
        self,
        *,
        user_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
        member_user_id: uuid.UUID | None = None,
    ) -> StreakResponse:
        subject_id = await resolve_metrics_subject(
            self._org_repo,
            caller_id=user_id,
            organization_id=organization_id,
            member_user_id=member_user_id,
        )
        tz = await self._user_tz(subject_id)
        key = f"metrics:streaks:v2:{subject_id}:{tz}"
        return await self._cached(
            key,
            StreakResponse,
            lambda: self._compute_streaks(user_id=subject_id, tz=tz),
        )

    async def _compute_streaks(
        self, *, user_id: uuid.UUID, tz: tzinfo
    ) -> StreakResponse:
        tasks = await self._metrics_repo.get_tasks_for_user(user_id)
        done_days = sorted(
            {_local_date(_completion_time(t), tz) for t in tasks if t.status == "done"}
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

        today = _local_date(datetime.now(UTC), tz)
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
        key = f"metrics:project:{user_id}:{project_id}"
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
            and t.status not in OVERDUE_EXCLUDED_STATUSES
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

    async def get_cycle_time(
        self, *, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> CycleTimeResponse:
        # No user_id in the key, unlike get_project_metrics's — the response
        # has no per-user filtering, so every authorized member shares one
        # cache entry instead of one each.
        key = f"metrics:cycle_time:{project_id}"
        return await self._cached(
            key,
            CycleTimeResponse,
            lambda: self._compute_cycle_time_response(
                project_id=project_id, user_id=user_id
            ),
        )

    async def _compute_cycle_time_response(
        self, *, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> CycleTimeResponse:
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
        changes = await self._status_change_repo.list_for_tasks([t.id for t in tasks])
        changes_by_task: dict[uuid.UUID, list[TaskStatusChange]] = defaultdict(list)
        for change in changes:
            changes_by_task[change.task_id].append(change)

        stages, stuck = _compute_cycle_time(tasks, changes_by_task, datetime.now(UTC))
        return CycleTimeResponse(project_id=project_id, stages=stages, stuck=stuck)


def get_metrics_service(
    session: AsyncSession = Depends(get_session),
    cache: CacheBackend = Depends(get_cache),
) -> MetricsService:
    settings = get_settings()
    return MetricsService(
        metrics_repo=MetricsRepository(session),
        project_repo=ProjectRepository(session),
        org_repo=OrganizationRepository(session),
        user_repo=UserRepository(session),
        status_change_repo=TaskStatusChangeRepository(session),
        cache=cache,
        ttl_seconds=settings.metrics_cache_ttl_seconds,
    )
