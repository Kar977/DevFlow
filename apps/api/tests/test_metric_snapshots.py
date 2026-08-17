"""MetricSnapshotService and /metrics/trends, /metrics/org-trends tests.

Covers the lazy-backfill algorithm: closed weeks are computed once and
persisted, the current (open) week is always live, and already-captured
closed weeks are never recomputed even if the underlying raw data would now
produce a different value.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from devflow_api.core.models.metric_snapshot import (
    ORG_METRIC_KEYS,
    USER_METRIC_KEYS,
    MetricSnapshot,
)
from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.models.pull_request import PullRequest
from devflow_api.core.models.task import Task
from devflow_api.core.models.user import User
from devflow_api.core.models.work_session import WorkSession
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.metric_snapshot import (
    MetricSnapshotService,
    get_metric_snapshot_service,
)
from devflow_api.core.services.period import week_start
from devflow_api.main import create_app

NOW = datetime.now(UTC)
CURRENT_WEEK = week_start(NOW)


def _week(offset: int) -> datetime:
    """UTC midnight of the Monday `offset` weeks before the current week."""
    day = CURRENT_WEEK - timedelta(days=7 * offset)
    return datetime.combine(day, datetime.min.time(), tzinfo=UTC)


def _task(
    *,
    status: str = "done",
    assignee_id: uuid.UUID | None = None,
    estimate_minutes: int | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> Task:
    moment = created_at or _week(1)
    return Task(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        title="T",
        description=None,
        status=status,
        priority="medium",
        estimate_minutes=estimate_minutes,
        assignee_id=assignee_id,
        due_date=None,
        github_pr_url=None,
        created_by=uuid.uuid4(),
        created_at=moment,
        updated_at=updated_at or moment,
        completed_at=completed_at,
    )


def _session(
    *, task_id: uuid.UUID, user_id: uuid.UUID, started_at: datetime, minutes: int
) -> WorkSession:
    return WorkSession(
        id=uuid.uuid4(),
        task_id=task_id,
        user_id=user_id,
        started_at=started_at,
        ended_at=started_at + timedelta(minutes=minutes),
        duration_seconds=minutes * 60,
        created_at=started_at,
    )


def _pr(
    *,
    state: str = "open",
    created_at_github: datetime,
    merged_at: datetime | None = None,
    first_review_at: datetime | None = None,
) -> PullRequest:
    return PullRequest(
        id=uuid.uuid4(),
        repository_id=uuid.uuid4(),
        github_pr_id=uuid.uuid4().int % 100000,
        number=1,
        title="PR",
        author_login="dev",
        state=state,
        created_at_github=created_at_github,
        merged_at=merged_at,
        closed_at=None,
        first_review_at=first_review_at,
        html_url="https://github.com/owner/repo/pull/1",
        last_synced_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


# ---------------------------------------------------------------------------
# Fake repositories
# ---------------------------------------------------------------------------


class FakeSnapshotRepo:
    def __init__(self) -> None:
        self.rows: list[MetricSnapshot] = []
        self.bulk_create_calls = 0

    async def list_for_user(
        self, user_id: uuid.UUID, *, period_from: datetime
    ) -> list[MetricSnapshot]:
        return [
            r
            for r in self.rows
            if r.scope == "user"
            and r.user_id == user_id
            and r.period_start >= period_from
        ]

    async def list_for_org(
        self, org_id: uuid.UUID, *, period_from: datetime
    ) -> list[MetricSnapshot]:
        return [
            r
            for r in self.rows
            if r.scope == "org" and r.org_id == org_id and r.period_start >= period_from
        ]

    async def delete_for_user(
        self, user_id: uuid.UUID, *, period_from: datetime | None = None
    ) -> int:
        keep = []
        removed = 0
        for r in self.rows:
            matches = (
                r.scope == "user"
                and r.user_id == user_id
                and (period_from is None or r.period_start >= period_from)
            )
            if matches:
                removed += 1
            else:
                keep.append(r)
        self.rows = keep
        return removed

    async def delete_for_org(
        self, org_id: uuid.UUID, *, period_from: datetime | None = None
    ) -> int:
        keep = []
        removed = 0
        for r in self.rows:
            matches = (
                r.scope == "org"
                and r.org_id == org_id
                and (period_from is None or r.period_start >= period_from)
            )
            if matches:
                removed += 1
            else:
                keep.append(r)
        self.rows = keep
        return removed

    async def bulk_create(self, rows: list[dict[str, object]]) -> None:
        self.bulk_create_calls += 1
        existing_keys = {
            (r.scope, r.user_id, r.org_id, r.metric_key, r.period_start)
            for r in self.rows
        }
        for row in rows:
            key = (
                row["scope"],
                row["user_id"],
                row["org_id"],
                row["metric_key"],
                row["period_start"],
            )
            if key in existing_keys:
                continue
            self.rows.append(MetricSnapshot(id=uuid.uuid4(), **row))
            existing_keys.add(key)  # type: ignore[arg-type]

    def seed(
        self,
        *,
        scope: str,
        metric_key: str,
        period_start: datetime,
        value: float | None,
        user_id: uuid.UUID | None = None,
        org_id: uuid.UUID | None = None,
    ) -> None:
        self.rows.append(
            MetricSnapshot(
                id=uuid.uuid4(),
                scope=scope,
                user_id=user_id,
                org_id=org_id,
                metric_key=metric_key,
                period_start=period_start,
                period_end=period_start + timedelta(days=7),
                metric_value=value,
            )
        )


class FakeMetricsRepo:
    def __init__(self) -> None:
        self.user_tasks: list[Task] = []
        self.user_sessions: list[WorkSession] = []
        self.get_tasks_calls = 0
        self.get_sessions_calls = 0

    async def get_tasks_for_user(self, user_id: uuid.UUID) -> list[Task]:
        self.get_tasks_calls += 1
        return self.user_tasks

    async def get_work_sessions_for_user(self, user_id: uuid.UUID) -> list[WorkSession]:
        self.get_sessions_calls += 1
        return self.user_sessions


class FakePRRepo:
    def __init__(self) -> None:
        self.prs: list[PullRequest] = []
        self.list_calls = 0

    async def list_for_org(
        self, org_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> list[PullRequest]:
        self.list_calls += 1
        return self.prs


class FakeUserRepo:
    def __init__(self, *, timezone: str | None = None) -> None:
        self._timezone = timezone

    async def get_by_id(self, user_id: uuid.UUID) -> User:
        return User(
            id=user_id,
            email="user@example.com",
            hashed_password="x",
            timezone=self._timezone,
            created_at=NOW,
            updated_at=NOW,
        )


class FakeOrgRepo:
    def __init__(self) -> None:
        self._members: dict[tuple[uuid.UUID, uuid.UUID], OrganizationMember] = {}

    def seed_member(self, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self._members[(org_id, user_id)] = OrganizationMember(
            id=uuid.uuid4(), org_id=org_id, user_id=user_id, role="owner", joined_at=NOW
        )

    async def get_member(
        self, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrganizationMember | None:
        return self._members.get((org_id, user_id))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def org_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def snapshot_repo() -> FakeSnapshotRepo:
    return FakeSnapshotRepo()


@pytest.fixture()
def metrics_repo() -> FakeMetricsRepo:
    return FakeMetricsRepo()


@pytest.fixture()
def pr_repo() -> FakePRRepo:
    return FakePRRepo()


@pytest.fixture()
def org_repo(org_id: uuid.UUID, user_id: uuid.UUID) -> FakeOrgRepo:
    repo = FakeOrgRepo()
    repo.seed_member(org_id, user_id)
    return repo


@pytest.fixture()
def user_repo() -> FakeUserRepo:
    """Default: no timezone set — every existing test keeps UTC bucketing."""
    return FakeUserRepo(timezone=None)


@pytest.fixture()
def service(
    snapshot_repo: FakeSnapshotRepo,
    metrics_repo: FakeMetricsRepo,
    pr_repo: FakePRRepo,
    org_repo: FakeOrgRepo,
    user_repo: FakeUserRepo,
) -> MetricSnapshotService:
    return MetricSnapshotService(
        snapshot_repo=snapshot_repo,  # type: ignore[arg-type]
        metrics_repo=metrics_repo,  # type: ignore[arg-type]
        pr_repo=pr_repo,  # type: ignore[arg-type]
        org_repo=org_repo,  # type: ignore[arg-type]
        user_repo=user_repo,  # type: ignore[arg-type]
    )


@pytest.fixture()
def client(user_id: uuid.UUID, service: MetricSnapshotService) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_metric_snapshot_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(user_id)
    )
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Backfill behavior (user scope)
# ---------------------------------------------------------------------------


async def test_backfill_writes_only_closed_weeks(
    service: MetricSnapshotService,
    snapshot_repo: FakeSnapshotRepo,
    metrics_repo: FakeMetricsRepo,
    user_id: uuid.UUID,
) -> None:
    metrics_repo.user_tasks = [_task(status="done", completed_at=_week(1))]
    result = await service.get_user_trends(user_id=user_id, weeks=4)

    # 4 points per series: 3 closed weeks + the current (live) week.
    for series in result.series:
        assert len(series.points) == 4
        assert series.points[-1].week_start == CURRENT_WEEK

    persisted_weeks = {r.period_start.date() for r in snapshot_repo.rows}
    assert CURRENT_WEEK not in persisted_weeks
    assert len(persisted_weeks) == 3  # the 3 closed weeks
    assert len(snapshot_repo.rows) == 3 * len(USER_METRIC_KEYS)


async def test_second_call_is_idempotent(
    service: MetricSnapshotService,
    snapshot_repo: FakeSnapshotRepo,
    metrics_repo: FakeMetricsRepo,
    user_id: uuid.UUID,
) -> None:
    metrics_repo.user_tasks = [_task(status="done", completed_at=_week(1))]
    await service.get_user_trends(user_id=user_id, weeks=4)
    row_count_after_first = len(snapshot_repo.rows)

    result = await service.get_user_trends(user_id=user_id, weeks=4)

    assert len(snapshot_repo.rows) == row_count_after_first
    velocity_series = next(
        s for s in result.series if s.metric_key == "tasks_completed"
    )
    by_week = {p.week_start: p.value for p in velocity_series.points}
    assert by_week[_week(1).date()] == 1.0


async def test_gap_is_filled_without_touching_existing_rows(
    service: MetricSnapshotService,
    snapshot_repo: FakeSnapshotRepo,
    metrics_repo: FakeMetricsRepo,
    user_id: uuid.UUID,
) -> None:
    """A pre-seeded week keeps its stored value even though the raw data
    (an empty task list) would now compute something different — proving
    closed weeks are immutable once captured."""
    for key in USER_METRIC_KEYS:
        snapshot_repo.seed(
            scope="user",
            user_id=user_id,
            metric_key=key,
            period_start=_week(2),
            value=999.0,
        )
    metrics_repo.user_tasks = []  # would compute 0.0/None for every metric

    result = await service.get_user_trends(user_id=user_id, weeks=4)

    for series in result.series:
        seeded_point = next(p for p in series.points if p.week_start == _week(2).date())
        assert seeded_point.value == 999.0
        # The other closed week (week offset 3) had no snapshot, so it was
        # backfilled fresh from the (empty) raw data.
        other_point = next(p for p in series.points if p.week_start == _week(3).date())
        assert other_point.value in (0.0, None)


async def test_recompute_overwrites_a_captured_week(
    service: MetricSnapshotService,
    snapshot_repo: FakeSnapshotRepo,
    metrics_repo: FakeMetricsRepo,
    user_id: uuid.UUID,
) -> None:
    """The inverse of `test_gap_is_filled_without_touching_existing_rows`:
    recompute is the one path allowed to overwrite an already-captured week
    with a fresh value from current raw data."""
    for key in USER_METRIC_KEYS:
        snapshot_repo.seed(
            scope="user",
            user_id=user_id,
            metric_key=key,
            period_start=_week(2),
            value=999.0,
        )
    metrics_repo.user_tasks = [_task(status="done", completed_at=_week(2))]

    result = await service.recompute_user_trends(user_id=user_id, weeks=4)

    tasks_completed = next(
        s for s in result.series if s.metric_key == "tasks_completed"
    )
    point = next(p for p in tasks_completed.points if p.week_start == _week(2).date())
    assert point.value == 1.0  # freshly computed, not the stale seeded 999.0

    # A normal read afterwards must see the same rebuilt value, not the old
    # seed — proving the row was actually replaced in storage, not just the
    # in-memory response.
    reread = await service.get_user_trends(user_id=user_id, weeks=4)
    reread_series = next(s for s in reread.series if s.metric_key == "tasks_completed")
    reread_point = next(
        p for p in reread_series.points if p.week_start == _week(2).date()
    )
    assert reread_point.value == 1.0


async def test_counting_metric_stores_zero_not_null(
    service: MetricSnapshotService,
    snapshot_repo: FakeSnapshotRepo,
    metrics_repo: FakeMetricsRepo,
    user_id: uuid.UUID,
) -> None:
    metrics_repo.user_tasks = []
    metrics_repo.user_sessions = []
    await service.get_user_trends(user_id=user_id, weeks=3)

    tasks_completed_rows = [
        r for r in snapshot_repo.rows if r.metric_key == "tasks_completed"
    ]
    active_hours_rows = [
        r for r in snapshot_repo.rows if r.metric_key == "active_hours"
    ]
    assert all(r.metric_value == 0.0 for r in tasks_completed_rows)
    assert all(r.metric_value == 0.0 for r in active_hours_rows)


async def test_ratio_metric_stores_null_without_samples(
    service: MetricSnapshotService,
    snapshot_repo: FakeSnapshotRepo,
    metrics_repo: FakeMetricsRepo,
    user_id: uuid.UUID,
) -> None:
    metrics_repo.user_tasks = []
    await service.get_user_trends(user_id=user_id, weeks=3)

    completion_rows = [
        r for r in snapshot_repo.rows if r.metric_key == "completion_rate"
    ]
    estimation_rows = [
        r for r in snapshot_repo.rows if r.metric_key == "estimation_ratio"
    ]
    assert all(r.metric_value is None for r in completion_rows)
    assert all(r.metric_value is None for r in estimation_rows)


async def test_tasks_completed_matches_per_week_completion_count(
    service: MetricSnapshotService,
    metrics_repo: FakeMetricsRepo,
    user_id: uuid.UUID,
) -> None:
    metrics_repo.user_tasks = [
        _task(status="done", completed_at=_week(1)),
        _task(status="done", completed_at=_week(1)),
        _task(status="done", completed_at=_week(2)),
    ]
    result = await service.get_user_trends(user_id=user_id, weeks=4)
    series = next(s for s in result.series if s.metric_key == "tasks_completed")
    by_week = {p.week_start: p.value for p in series.points}
    assert by_week[_week(1).date()] == 2.0
    assert by_week[_week(2).date()] == 1.0
    assert by_week[_week(3).date()] == 0.0


async def test_series_length_and_order_match_horizon(
    service: MetricSnapshotService, user_id: uuid.UUID
) -> None:
    result = await service.get_user_trends(user_id=user_id, weeks=6)
    assert result.weeks == 6
    for series in result.series:
        assert len(series.points) == 6
        week_starts = [p.week_start for p in series.points]
        assert week_starts == sorted(week_starts)
        assert week_starts[-1] == CURRENT_WEEK


# ---------------------------------------------------------------------------
# Timezone-aware grid (user scope only)
# ---------------------------------------------------------------------------


async def test_user_scope_period_start_is_local_monday_midnight_in_utc(
    snapshot_repo: FakeSnapshotRepo,
    metrics_repo: FakeMetricsRepo,
    pr_repo: FakePRRepo,
    org_repo: FakeOrgRepo,
    user_id: uuid.UUID,
) -> None:
    """A Warsaw user's captured week must be keyed by their local Monday
    midnight (expressed as a UTC instant), not the UTC-anchored grid."""
    service = MetricSnapshotService(
        snapshot_repo=snapshot_repo,  # type: ignore[arg-type]
        metrics_repo=metrics_repo,  # type: ignore[arg-type]
        pr_repo=pr_repo,  # type: ignore[arg-type]
        org_repo=org_repo,  # type: ignore[arg-type]
        user_repo=FakeUserRepo(timezone="Europe/Warsaw"),  # type: ignore[arg-type]
    )
    metrics_repo.user_tasks = [_task(status="done", completed_at=_week(1))]

    await service.get_user_trends(user_id=user_id, weeks=4)

    persisted_starts = sorted(r.period_start for r in snapshot_repo.rows)
    # Europe/Warsaw is UTC+1 (CET) or UTC+2 (CEST); local midnight can never
    # itself be 00:00 UTC.
    assert all(ts.hour != 0 or ts.minute != 0 for ts in persisted_starts)
    warsaw = ZoneInfo("Europe/Warsaw")
    for ts in persisted_starts:
        local = ts.astimezone(warsaw)
        assert local.hour == 0
        assert local.weekday() == 0  # Monday


# ---------------------------------------------------------------------------
# Recompute route
# ---------------------------------------------------------------------------


def test_recompute_route_returns_fresh_series(client: TestClient) -> None:
    response = client.post("/api/v1/metrics/trends/recompute?weeks=4")
    assert response.status_code == 200
    body = response.json()
    assert body["weeks"] == 4
    assert len(body["series"]) == len(USER_METRIC_KEYS)


def test_recompute_route_requires_auth() -> None:
    app = create_app()
    with TestClient(app) as c:
        response = c.post("/api/v1/metrics/trends/recompute")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Org scope
# ---------------------------------------------------------------------------


async def test_org_trends_rejects_non_member(
    snapshot_repo: FakeSnapshotRepo,
    metrics_repo: FakeMetricsRepo,
    pr_repo: FakePRRepo,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from devflow_api.core.errors import AppError

    service = MetricSnapshotService(
        snapshot_repo=snapshot_repo,  # type: ignore[arg-type]
        metrics_repo=metrics_repo,  # type: ignore[arg-type]
        pr_repo=pr_repo,  # type: ignore[arg-type]
        org_repo=FakeOrgRepo(),  # type: ignore[arg-type]  # no membership seeded
        user_repo=FakeUserRepo(),  # type: ignore[arg-type]
    )
    with pytest.raises(AppError) as exc_info:
        await service.get_org_trends(org_id=org_id, user_id=user_id, weeks=4)
    assert exc_info.value.status_code == 403


async def test_org_trends_backfills_pr_flow_kpis(
    service: MetricSnapshotService,
    snapshot_repo: FakeSnapshotRepo,
    pr_repo: FakePRRepo,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    pr_repo.prs = [
        _pr(state="merged", created_at_github=_week(1), merged_at=_week(1)),
        _pr(state="open", created_at_github=_week(1)),
    ]
    result = await service.get_org_trends(org_id=org_id, user_id=user_id, weeks=4)

    opened = next(s for s in result.series if s.metric_key == "pr_opened")
    merged = next(s for s in result.series if s.metric_key == "pr_merged")
    by_week_opened = {p.week_start: p.value for p in opened.points}
    by_week_merged = {p.week_start: p.value for p in merged.points}
    assert by_week_opened[_week(1).date()] == 2.0
    assert by_week_merged[_week(1).date()] == 1.0

    persisted_weeks = {r.period_start.date() for r in snapshot_repo.rows}
    assert CURRENT_WEEK not in persisted_weeks
    assert {k for r in snapshot_repo.rows for k in [r.metric_key]} <= set(
        ORG_METRIC_KEYS
    )


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


async def test_cache_hit_avoids_second_raw_fetch(
    snapshot_repo: FakeSnapshotRepo,
    metrics_repo: FakeMetricsRepo,
    pr_repo: FakePRRepo,
    org_repo: FakeOrgRepo,
    user_id: uuid.UUID,
) -> None:
    from devflow_api.core.cache import InMemoryCache

    cache = InMemoryCache()
    service = MetricSnapshotService(
        snapshot_repo=snapshot_repo,  # type: ignore[arg-type]
        metrics_repo=metrics_repo,  # type: ignore[arg-type]
        pr_repo=pr_repo,  # type: ignore[arg-type]
        org_repo=org_repo,  # type: ignore[arg-type]
        user_repo=FakeUserRepo(),  # type: ignore[arg-type]
        cache=cache,
    )
    await service.get_user_trends(user_id=user_id, weeks=4)
    await service.get_user_trends(user_id=user_id, weeks=4)
    assert metrics_repo.get_tasks_calls == 1
    assert metrics_repo.get_sessions_calls == 1


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def test_trends_route_returns_expected_shape(client: TestClient) -> None:
    response = client.get("/api/v1/metrics/trends?weeks=4")
    assert response.status_code == 200
    body = response.json()
    assert body["weeks"] == 4
    assert len(body["series"]) == len(USER_METRIC_KEYS)
    assert len(body["series"][0]["points"]) == 4


def test_trends_route_rejects_weeks_below_minimum(client: TestClient) -> None:
    response = client.get("/api/v1/metrics/trends?weeks=1")
    assert response.status_code == 422


def test_trends_route_rejects_weeks_above_maximum(client: TestClient) -> None:
    response = client.get("/api/v1/metrics/trends?weeks=105")
    assert response.status_code == 422


def test_trends_route_requires_auth() -> None:
    app = create_app()
    with TestClient(app) as c:
        response = c.get("/api/v1/metrics/trends")
    assert response.status_code == 401


def test_org_trends_route_requires_org_id(client: TestClient) -> None:
    response = client.get("/api/v1/metrics/org-trends")
    assert response.status_code == 422


def test_org_trends_route_returns_expected_shape(
    client: TestClient, org_id: uuid.UUID
) -> None:
    response = client.get(
        f"/api/v1/metrics/org-trends?organization_id={org_id}&weeks=4"
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["series"]) == len(ORG_METRIC_KEYS)


def test_org_trends_route_rejects_non_member(client: TestClient) -> None:
    foreign_org = uuid.uuid4()
    response = client.get(f"/api/v1/metrics/org-trends?organization_id={foreign_org}")
    assert response.status_code == 403
