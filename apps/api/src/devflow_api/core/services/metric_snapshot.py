"""MetricSnapshotService — long-range weekly trends, backed by lazy snapshots.

Unlike `MetricsService`/`PRMetricsService` (always "current vs previous
period"), this service answers "show me the last N weeks" by combining two
sources per week:

- **Closed weeks** (fully elapsed ISO weeks) are read from `metric_snapshots`
  when already captured, or computed once and persisted the first time
  they're requested — see `_user_weekly_values`/`_org_weekly_values`. Once
  captured, a closed week's value is treated as immutable: a later edit to
  the source data (e.g. a task's `completed_at` changing) will not update an
  already-persisted snapshot. There is no scheduler in this codebase to
  capture weeks proactively, so this lazy-write-on-read is the only capture
  path.
- The **current, still-open week** is always computed live and never
  persisted — persisting a partial week would permanently record an
  incomplete value under that week's key.

Both the backfill and the live-week value are computed from the same single
fetch of raw rows (`MetricsRepository`/`PullRequestRepository` — neither
supports server-side date filtering, so a full fetch already happens on
every read; snapshots save the aggregation work on repeat requests via the
cache layer, not the fetch itself).

`stale_pr_count` (the 5th PR-flow KPI) is deliberately not part of
`ORG_METRIC_KEYS` — it's a point-in-time reading that can't be reconstructed
for a past week from today's data.

Timezone and recompute
-----------------------
User-scope weeks bucket by the *user's* local time (`period_start` is that
user's local Monday midnight, expressed as a UTC instant — matches
`MetricsService`). Org scope has no single user to anchor to and stays
UTC-anchored, like `PRMetricsService`. Because a user's stored timezone can
change and move their whole week grid, and because "closed weeks are
immutable" would otherwise make a bad snapshot permanent,
`recompute_user_trends` deletes a user's captured rows in the horizon and
lets the normal lazy backfill in `_compute_user_trends` rewrite them — used
both for a manual "my chart looks wrong" recompute (``POST
/metrics/trends/recompute``) and as the repair step right after a timezone
change. User scope only: org trends have no recompute route, since any
member could force an org-wide rewrite (`delete_for_org` exists on the
repository for symmetry but nothing calls it yet).
"""

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta, tzinfo

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.cache import CacheBackend, get_cache
from devflow_api.core.config import get_settings
from devflow_api.core.database import get_session
from devflow_api.core.models.metric_snapshot import ORG_METRIC_KEYS, USER_METRIC_KEYS
from devflow_api.core.models.pull_request import PullRequest
from devflow_api.core.models.task import Task
from devflow_api.core.models.work_session import WorkSession
from devflow_api.core.repositories.metric_snapshot import MetricSnapshotRepository
from devflow_api.core.repositories.metrics import MetricsRepository
from devflow_api.core.repositories.organization import OrganizationRepository
from devflow_api.core.repositories.pull_request import PullRequestRepository
from devflow_api.core.repositories.user import UserRepository
from devflow_api.core.schemas.metrics import (
    MetricTrendPointResponse,
    MetricTrendSeriesResponse,
    MetricTrendsResponse,
)
from devflow_api.core.services.cache_aside import cached
from devflow_api.core.services.org_access import require_member
from devflow_api.core.services.period import (
    as_utc,
    day_start_utc,
    resolve_tz,
    week_start,
)
from devflow_api.core.services.pr_metrics import (
    _review_ratio,
    _review_velocity,
    _round_or_none,
)

_DEFAULT_TRENDS_WEEKS = 26


# ---------------------------------------------------------------------------
# Pure helpers (no state)
# ---------------------------------------------------------------------------


def _week_datetime(day: date) -> datetime:
    """UTC-anchored Monday midnight — org scope only (no single user's tz)."""
    return datetime.combine(day, datetime.min.time(), tzinfo=UTC)


def _horizon(now: datetime, weeks: int, tz: tzinfo = UTC) -> tuple[list[date], date]:
    """Return (closed_weeks, current_week) covering *weeks* points total.

    ``closed_weeks`` has ``weeks - 1`` entries, oldest first, each a fully
    elapsed ISO week; ``current_week`` is the still-open week the horizon
    ends on. Both are computed in *tz* — org calls leave it at UTC.
    """
    current = week_start(now, tz)
    last_closed = current - timedelta(days=7)
    first_closed = last_closed - timedelta(days=7 * (weeks - 2))
    closed: list[date] = []
    cursor = first_closed
    while cursor <= last_closed:
        closed.append(cursor)
        cursor += timedelta(days=7)
    return closed, current


def _user_weekly_values(
    tasks: list[Task], sessions: list[WorkSession], weeks: list[date], tz: tzinfo
) -> dict[date, dict[str, float | None]]:
    """Compute each of USER_METRIC_KEYS for every week in *weeks*.

    Mirrors the formulas in ``MetricsService`` (``_compute_velocity`` for
    ``tasks_completed``, ``_compute_time_tracking`` for ``active_hours``,
    ``_compute_completion_rate`` for ``completion_rate``,
    ``_compute_estimation_accuracy`` for ``estimation_ratio``), bucketed by
    the user's local ISO week instead of a single current/previous window.
    """
    done_by_week: dict[date, list[Task]] = {w: [] for w in weeks}
    created_by_week: dict[date, list[Task]] = {w: [] for w in weeks}
    minutes_by_week: dict[date, float] = dict.fromkeys(weeks, 0.0)
    actual_minutes_by_task: dict[uuid.UUID, float] = defaultdict(float)

    for session in sessions:
        if not session.duration_seconds:
            continue
        actual_minutes_by_task[session.task_id] += session.duration_seconds / 60
        bucket = week_start(session.started_at, tz)
        if bucket in minutes_by_week:
            minutes_by_week[bucket] += session.duration_seconds / 60

    for task in tasks:
        created_bucket = week_start(task.created_at, tz)
        if created_bucket in created_by_week:
            created_by_week[created_bucket].append(task)
        if task.status == "done":
            done_bucket = week_start(task.completed_at or task.updated_at, tz)
            if done_bucket in done_by_week:
                done_by_week[done_bucket].append(task)

    result: dict[date, dict[str, float | None]] = {}
    for week in weeks:
        done_tasks = done_by_week[week]
        created_tasks = created_by_week[week]
        created_done = sum(1 for t in created_tasks if t.status == "done")

        ratios: list[float] = []
        for task in done_tasks:
            if not task.estimate_minutes:
                continue
            actual = actual_minutes_by_task.get(task.id, 0)
            if actual:
                ratios.append(actual / task.estimate_minutes)

        result[week] = {
            "tasks_completed": float(len(done_tasks)),
            "active_hours": round(minutes_by_week[week] / 60, 2),
            "completion_rate": (
                round(created_done / len(created_tasks) * 100, 2)
                if created_tasks
                else None
            ),
            "estimation_ratio": (
                round(sum(ratios) / len(ratios), 2) if ratios else None
            ),
        }
    return result


def _build_series(
    metric_keys: tuple[str, ...],
    closed_weeks: list[date],
    current_week: date,
    existing_map: dict[tuple[str, date], float | None],
    computed: dict[date, dict[str, float | None]],
) -> list[MetricTrendSeriesResponse]:
    """Assemble one zero-filled series per metric key.

    Closed weeks prefer the persisted value (``existing_map``) over a fresh
    recompute — a captured week is immutable — falling back to ``computed``
    only for weeks not yet backed by a snapshot row. The current week always
    comes from ``computed`` (see module docstring: never persisted).
    """
    series = []
    for metric_key in metric_keys:
        points = [
            MetricTrendPointResponse(
                week_start=week,
                value=existing_map.get((metric_key, week), computed[week][metric_key]),
            )
            for week in closed_weeks
        ]
        points.append(
            MetricTrendPointResponse(
                week_start=current_week, value=computed[current_week][metric_key]
            )
        )
        series.append(MetricTrendSeriesResponse(metric_key=metric_key, points=points))
    return series


def _org_weekly_values(
    prs: list[PullRequest], weeks: list[date]
) -> dict[date, dict[str, float | None]]:
    """Compute each of ORG_METRIC_KEYS for every week in *weeks*.

    ``pr_opened``/``pr_merged`` bucket like ``_build_pr_trends``'s
    opened/merged counts; ``review_velocity_h`` reuses
    ``PRMetricsService._review_velocity`` windowed to the week;
    ``review_ratio`` reuses ``_review_ratio`` over the week's opened cohort.
    """
    opened_by_week: dict[date, list[PullRequest]] = {w: [] for w in weeks}
    merged_count: dict[date, int] = dict.fromkeys(weeks, 0)

    for pr in prs:
        opened_bucket = week_start(pr.created_at_github)
        if opened_bucket in opened_by_week:
            opened_by_week[opened_bucket].append(pr)
        if pr.state == "merged" and pr.merged_at is not None:
            merged_bucket = week_start(pr.merged_at)
            if merged_bucket in merged_count:
                merged_count[merged_bucket] += 1

    result: dict[date, dict[str, float | None]] = {}
    for week in weeks:
        cohort = opened_by_week[week]
        window_start = _week_datetime(week)
        window_end = _week_datetime(week + timedelta(days=7))
        result[week] = {
            "pr_opened": float(len(cohort)),
            "pr_merged": float(merged_count[week]),
            "review_velocity_h": _round_or_none(
                _review_velocity(prs, window_start, window_end)
            ),
            "review_ratio": _round_or_none(_review_ratio(cohort)),
        }
    return result


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class MetricSnapshotService:
    def __init__(
        self,
        snapshot_repo: MetricSnapshotRepository,
        metrics_repo: MetricsRepository,
        pr_repo: PullRequestRepository,
        org_repo: OrganizationRepository,
        user_repo: UserRepository,
        cache: CacheBackend | None = None,
        ttl_seconds: int = 60,
    ) -> None:
        self._snapshot_repo = snapshot_repo
        self._metrics_repo = metrics_repo
        self._pr_repo = pr_repo
        self._org_repo = org_repo
        self._user_repo = user_repo
        self._cache = cache
        self._ttl_seconds = ttl_seconds

    async def _user_tz(self, user_id: uuid.UUID) -> tzinfo:
        """Resolve the user's stored IANA zone, defaulting to UTC.

        Mirrors ``MetricsService._user_tz`` — see that docstring. Called
        before the cache key is built, so a timezone change (which moves
        the whole week grid) self-heals on the next read instead of serving
        another grid's numbers for the cache TTL.
        """
        user = await self._user_repo.get_by_id(user_id)
        return resolve_tz(user.timezone if user is not None else None)

    async def get_user_trends(
        self, *, user_id: uuid.UUID, weeks: int = _DEFAULT_TRENDS_WEEKS
    ) -> MetricTrendsResponse:
        tz = await self._user_tz(user_id)
        # "v2": adds the tz name to the key (v1 was UTC-only).
        key = f"metrics:trends:v2:user:{user_id}:{tz}:{weeks}"
        return await cached(
            self._cache,
            key,
            MetricTrendsResponse,
            self._ttl_seconds,
            lambda: self._compute_user_trends(user_id=user_id, weeks=weeks, tz=tz),
        )

    async def _compute_user_trends(
        self, *, user_id: uuid.UUID, weeks: int, tz: tzinfo
    ) -> MetricTrendsResponse:
        now = datetime.now(UTC)
        closed_weeks, current_week = _horizon(now, weeks, tz)

        existing = await self._snapshot_repo.list_for_user(
            user_id, period_from=day_start_utc(closed_weeks[0], tz)
        )
        existing_map: dict[tuple[str, date], float | None] = {
            (row.metric_key, week_start(row.period_start, tz)): row.metric_value
            for row in existing
        }

        tasks = await self._metrics_repo.get_tasks_for_user(user_id)
        sessions = await self._metrics_repo.get_work_sessions_for_user(user_id)
        computed = _user_weekly_values(
            tasks, sessions, [*closed_weeks, current_week], tz
        )

        rows = [
            {
                "scope": "user",
                "user_id": user_id,
                "org_id": None,
                "metric_key": metric_key,
                "period_start": day_start_utc(week, tz),
                "period_end": day_start_utc(week + timedelta(days=7), tz),
                "metric_value": computed[week][metric_key],
            }
            for week in closed_weeks
            for metric_key in USER_METRIC_KEYS
            if (metric_key, week) not in existing_map
        ]
        await self._snapshot_repo.bulk_create(rows)

        series = _build_series(
            USER_METRIC_KEYS, closed_weeks, current_week, existing_map, computed
        )
        return MetricTrendsResponse(
            period_from=day_start_utc(closed_weeks[0], tz),
            period_to=as_utc(now),
            weeks=weeks,
            series=series,
        )

    async def recompute_user_trends(
        self, *, user_id: uuid.UUID, weeks: int = _DEFAULT_TRENDS_WEEKS
    ) -> MetricTrendsResponse:
        """Drop this user's captured snapshots in the horizon and rebuild.

        The only escape from ``_build_series``'s "a captured week is
        immutable" rule — see the module docstring. Also the repair step a
        timezone change takes, since that moves the week grid itself.
        Deletes, clears the cache, then delegates to
        ``_compute_user_trends``, whose existing lazy backfill rewrites the
        rows — no duplicated aggregation logic.
        """
        tz = await self._user_tz(user_id)
        now = datetime.now(UTC)
        closed_weeks, _current_week = _horizon(now, weeks, tz)

        await self._snapshot_repo.delete_for_user(
            user_id, period_from=day_start_utc(closed_weeks[0], tz)
        )
        if self._cache is not None:
            await self._cache.delete_matching(str(user_id))

        return await self._compute_user_trends(user_id=user_id, weeks=weeks, tz=tz)

    async def get_org_trends(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        weeks: int = _DEFAULT_TRENDS_WEEKS,
    ) -> MetricTrendsResponse:
        # Authorization must never be served from cache.
        await require_member(self._org_repo, org_id, user_id)

        key = f"metrics:trends:v1:org:{org_id}:{weeks}"
        return await cached(
            self._cache,
            key,
            MetricTrendsResponse,
            self._ttl_seconds,
            lambda: self._compute_org_trends(org_id=org_id, weeks=weeks),
        )

    async def _compute_org_trends(
        self, *, org_id: uuid.UUID, weeks: int
    ) -> MetricTrendsResponse:
        now = datetime.now(UTC)
        closed_weeks, current_week = _horizon(now, weeks)

        existing = await self._snapshot_repo.list_for_org(
            org_id, period_from=_week_datetime(closed_weeks[0])
        )
        existing_map: dict[tuple[str, date], float | None] = {
            (row.metric_key, as_utc(row.period_start).date()): row.metric_value
            for row in existing
        }

        prs = await self._pr_repo.list_for_org(org_id, limit=1000, offset=0)
        computed = _org_weekly_values(prs, [*closed_weeks, current_week])

        rows = [
            {
                "scope": "org",
                "user_id": None,
                "org_id": org_id,
                "metric_key": metric_key,
                "period_start": _week_datetime(week),
                "period_end": _week_datetime(week + timedelta(days=7)),
                "metric_value": computed[week][metric_key],
            }
            for week in closed_weeks
            for metric_key in ORG_METRIC_KEYS
            if (metric_key, week) not in existing_map
        ]
        await self._snapshot_repo.bulk_create(rows)

        series = _build_series(
            ORG_METRIC_KEYS, closed_weeks, current_week, existing_map, computed
        )
        return MetricTrendsResponse(
            period_from=_week_datetime(closed_weeks[0]),
            period_to=as_utc(now),
            weeks=weeks,
            series=series,
        )


def get_metric_snapshot_service(
    session: AsyncSession = Depends(get_session),
    cache: CacheBackend = Depends(get_cache),
) -> MetricSnapshotService:
    settings = get_settings()
    return MetricSnapshotService(
        snapshot_repo=MetricSnapshotRepository(session),
        metrics_repo=MetricsRepository(session),
        pr_repo=PullRequestRepository(session),
        user_repo=UserRepository(session),
        org_repo=OrganizationRepository(session),
        cache=cache,
        ttl_seconds=settings.metrics_cache_ttl_seconds,
    )
